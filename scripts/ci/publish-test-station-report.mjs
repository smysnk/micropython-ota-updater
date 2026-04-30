#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_REPORT_PATH = './artifacts/test-station/report.json';

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const reportPath = args.input || process.env.TEST_STATION_INGEST_INPUT || DEFAULT_REPORT_PATH;
  const endpoint = args.endpoint || process.env.TEST_STATION_INGEST_ENDPOINT;
  const sharedKey = args.sharedKey || process.env.TEST_STATION_INGEST_SHARED_KEY;
  const projectKey = args.projectKey || process.env.TEST_STATION_INGEST_PROJECT_KEY || 'micropython-ota-updater';

  if (!endpoint) {
    throw new Error('Missing TEST_STATION_INGEST_ENDPOINT or --endpoint.');
  }
  if (!sharedKey) {
    throw new Error('Missing TEST_STATION_INGEST_SHARED_KEY or --shared-key.');
  }

  const outputDir = path.dirname(path.resolve(reportPath));
  const storage = normalizeStorageOptions({
    bucket: args.artifactS3Bucket || process.env.S3_BUCKET,
    prefix: args.artifactStoragePrefix || process.env.S3_STORAGE_PREFIX,
    baseUrl: args.artifactBaseUrl || process.env.S3_PUBLIC_URL,
  });
  const payload = {
    projectKey,
    report: attachArtifactLocations(readJson(reportPath), storage),
    source: buildGitHubSource({
      buildStartedAt: args.buildStartedAt || process.env.TEST_STATION_BUILD_STARTED_AT,
      buildCompletedAt: args.buildCompletedAt || process.env.TEST_STATION_BUILD_COMPLETED_AT,
      jobStatus: args.jobStatus || process.env.TEST_STATION_CI_STATUS,
      artifactCount: countOutputFiles(outputDir),
      storage,
    }),
    artifacts: collectOutputArtifacts(outputDir, storage),
  };

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      authorization: `Bearer ${sharedKey}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  const text = await response.text();
  const body = tryParseJson(text);

  if (!response.ok) {
    const detail = body?.error?.message || body?.message || text || `HTTP ${response.status}`;
    throw new Error(`Test Station ingest publish failed (${response.status}): ${detail}`);
  }

  process.stdout.write(`Published ${projectKey}:${payload.source.provider}:${payload.source.runId || 'manual'} to ${endpoint}\n`);
  if (body?.runId) {
    process.stdout.write(`runId=${body.runId}\n`);
  }
}

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    const value = argv[index + 1];
    switch (token) {
      case '--input':
        parsed.input = value;
        index += 1;
        break;
      case '--endpoint':
        parsed.endpoint = value;
        index += 1;
        break;
      case '--project-key':
        parsed.projectKey = value;
        index += 1;
        break;
      case '--shared-key':
        parsed.sharedKey = value;
        index += 1;
        break;
      case '--build-started-at':
        parsed.buildStartedAt = value;
        index += 1;
        break;
      case '--build-completed-at':
        parsed.buildCompletedAt = value;
        index += 1;
        break;
      case '--job-status':
        parsed.jobStatus = value;
        index += 1;
        break;
      case '--artifact-base-url':
        parsed.artifactBaseUrl = value;
        index += 1;
        break;
      case '--artifact-storage-prefix':
        parsed.artifactStoragePrefix = value;
        index += 1;
        break;
      case '--artifact-s3-bucket':
        parsed.artifactS3Bucket = value;
        index += 1;
        break;
      case '--help':
      case '-h':
        printUsage();
        process.exit(0);
        break;
      default:
        throw new Error(`Unknown argument: ${token}`);
    }
  }
  return parsed;
}

function printUsage() {
  process.stdout.write([
    'Usage: publish-test-station-report [options]',
    '',
    'Options:',
    '  --input <report.json>',
    '  --endpoint <https://host/api/ingest>',
    '  --project-key <project-key>',
    '  --shared-key <shared-key>',
    '  --build-started-at <iso8601>',
    '  --build-completed-at <iso8601>',
    '  --job-status <passed|failed>',
    '  --artifact-base-url <https://cdn.example.com/path>',
    '  --artifact-storage-prefix <prefix>',
    '  --artifact-s3-bucket <bucket>',
  ].join('\n'));
  process.stdout.write('\n');
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(path.resolve(filePath), 'utf8'));
}

function buildGitHubSource(options = {}, env = process.env) {
  const event = readGitHubEvent(env.GITHUB_EVENT_PATH);
  const serverUrl = trimToNull(env.GITHUB_SERVER_URL) || 'https://github.com';
  const repository = trimToNull(event?.repository?.full_name) || trimToNull(env.GITHUB_REPOSITORY);
  const repositoryUrl = trimToNull(event?.repository?.html_url) || (repository ? `${serverUrl}/${repository}` : null);
  const runId = trimToNull(env.GITHUB_RUN_ID);
  const startedAt = normalizeTimestamp(options.buildStartedAt) || new Date().toISOString();
  const completedAt = normalizeTimestamp(options.buildCompletedAt) || new Date().toISOString();
  const tag = resolveTag(env, event);
  const storage = normalizeStorageOptions(options.storage);

  return {
    provider: 'github-actions',
    runId,
    runUrl: repository && runId ? `${serverUrl}/${repository}/actions/runs/${runId}` : null,
    repositoryUrl,
    repository,
    defaultBranch: trimToNull(event?.repository?.default_branch),
    branch: resolveBranch(env, event),
    tag,
    commitSha: trimToNull(env.GITHUB_SHA),
    actor: trimToNull(env.GITHUB_ACTOR),
    startedAt,
    completedAt,
    buildNumber: parseInteger(env.GITHUB_RUN_NUMBER),
    semanticVersion: tag && /^v?\d+\.\d+\.\d+([-.+].+)?$/.test(tag) ? tag.replace(/^v/, '') : null,
    releaseName: tag,
    versionKey: tag ? `tag:${tag}` : null,
    ci: {
      eventName: trimToNull(env.GITHUB_EVENT_NAME),
      workflow: trimToNull(env.GITHUB_WORKFLOW),
      workflowRef: trimToNull(env.GITHUB_WORKFLOW_REF),
      workflowSha: trimToNull(env.GITHUB_WORKFLOW_SHA),
      job: trimToNull(env.GITHUB_JOB),
      ref: trimToNull(env.GITHUB_REF),
      refName: trimToNull(env.GITHUB_REF_NAME),
      refType: trimToNull(env.GITHUB_REF_TYPE),
      runAttempt: parseInteger(env.GITHUB_RUN_ATTEMPT),
      repositoryOwner: trimToNull(env.GITHUB_REPOSITORY_OWNER),
      serverUrl,
      status: trimToNull(options.jobStatus),
      buildDurationMs: diffTimestamps(startedAt, completedAt),
      artifactCount: Number.isFinite(options.artifactCount) ? options.artifactCount : null,
      environment: captureSafeCiEnvironment(env),
      storage: {
        bucket: storage.bucket,
        prefix: storage.prefix,
        baseUrl: storage.baseUrl,
      },
    },
  };
}

function resolveBranch(env, event) {
  return trimToNull(env.GITHUB_HEAD_REF)
    || trimToNull(event?.pull_request?.head?.ref)
    || (trimToNull(env.GITHUB_REF_TYPE) === 'branch' ? trimToNull(env.GITHUB_REF_NAME) : null);
}

function resolveTag(env, event) {
  return (trimToNull(env.GITHUB_REF_TYPE) === 'tag' ? trimToNull(env.GITHUB_REF_NAME) : null)
    || trimToNull(event?.release?.tag_name);
}

function readGitHubEvent(eventPath) {
  if (!trimToNull(eventPath) || !fs.existsSync(eventPath)) {
    return {};
  }
  try {
    return readJson(eventPath);
  } catch {
    return {};
  }
}

function captureSafeCiEnvironment(env) {
  const keys = [
    'CI',
    'GITHUB_ACTION',
    'GITHUB_ACTOR',
    'GITHUB_BASE_REF',
    'GITHUB_EVENT_NAME',
    'GITHUB_HEAD_REF',
    'GITHUB_JOB',
    'GITHUB_REF',
    'GITHUB_REF_NAME',
    'GITHUB_REF_TYPE',
    'GITHUB_REPOSITORY',
    'GITHUB_REPOSITORY_OWNER',
    'GITHUB_RUN_ATTEMPT',
    'GITHUB_RUN_ID',
    'GITHUB_RUN_NUMBER',
    'GITHUB_SHA',
    'GITHUB_WORKFLOW',
    'GITHUB_WORKFLOW_REF',
    'GITHUB_WORKFLOW_SHA',
    'RUNNER_ARCH',
    'RUNNER_NAME',
    'RUNNER_OS',
    'RUNNER_TEMP',
    'RUNNER_TOOL_CACHE',
  ];
  return Object.fromEntries(keys.filter((key) => trimToNull(env[key])).map((key) => [key, env[key]]));
}

function collectOutputArtifacts(outputDir, storage = {}) {
  return listFilesRecursively(path.resolve(outputDir))
    .map((absolutePath) => toRelativePosixPath(outputDir, absolutePath))
    .sort((left, right) => left.localeCompare(right))
    .map((relativePath) => {
      const locator = createArtifactLocator(relativePath, storage);
      return {
        label: createArtifactLabel(relativePath),
        relativePath,
        href: relativePath,
        kind: 'file',
        mediaType: inferMediaType(relativePath),
        storageKey: locator.storageKey,
        sourceUrl: locator.sourceUrl,
      };
    });
}

function attachArtifactLocations(report, storage = {}) {
  const cloned = structuredClone(report);
  for (const packageEntry of Array.isArray(cloned?.packages) ? cloned.packages : []) {
    for (const suite of Array.isArray(packageEntry?.suites) ? packageEntry.suites : []) {
      for (const artifact of Array.isArray(suite?.rawArtifacts) ? suite.rawArtifacts : []) {
        if (!artifact?.relativePath) {
          continue;
        }
        const locator = createArtifactLocator(path.posix.join('raw', normalizeRelativePath(artifact.relativePath)), storage);
        artifact.storageKey = locator.storageKey;
        artifact.sourceUrl = locator.sourceUrl;
      }
    }
  }
  return cloned;
}

function listFilesRecursively(rootDir) {
  if (!fs.existsSync(rootDir)) {
    return [];
  }
  const files = [];
  for (const entry of fs.readdirSync(rootDir, { withFileTypes: true })) {
    const absolutePath = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      files.push(...listFilesRecursively(absolutePath));
    } else if (entry.isFile()) {
      files.push(absolutePath);
    }
  }
  return files;
}

function countOutputFiles(outputDir) {
  return listFilesRecursively(outputDir).length;
}

function toRelativePosixPath(baseDir, absolutePath) {
  return normalizeRelativePath(path.relative(path.resolve(baseDir), absolutePath));
}

function createArtifactLabel(relativePath) {
  switch (relativePath) {
    case 'report.json':
      return 'Normalized report';
    case 'modules.json':
      return 'Module rollup';
    case 'ownership.json':
      return 'Ownership rollup';
    case 'index.html':
      return 'HTML report';
    default:
      return path.posix.basename(relativePath);
  }
}

function inferMediaType(relativePath) {
  const extension = path.extname(relativePath).toLowerCase();
  switch (extension) {
    case '.json':
      return 'application/json';
    case '.html':
      return 'text/html';
    case '.log':
    case '.txt':
      return 'text/plain';
    case '.ndjson':
      return 'application/x-ndjson';
    case '.zip':
      return 'application/zip';
    case '.png':
      return 'image/png';
    default:
      return null;
  }
}

function createArtifactLocator(relativePath, storage = {}) {
  const normalizedRelativePath = normalizeRelativePath(relativePath);
  const prefix = normalizeRelativePath(storage.prefix || '');
  const objectPath = prefix ? path.posix.join(prefix, normalizedRelativePath) : normalizedRelativePath;
  return {
    storageKey: storage.bucket ? `s3://${storage.bucket}/${objectPath}` : null,
    sourceUrl: storage.baseUrl ? new URL(objectPath, `${storage.baseUrl}/`).toString() : null,
  };
}

function normalizeStorageOptions(storage = {}) {
  return {
    bucket: trimToNull(storage.bucket),
    prefix: normalizeRelativePath(storage.prefix || ''),
    baseUrl: normalizeBaseUrl(storage.baseUrl),
  };
}

function normalizeRelativePath(value) {
  return String(value || '').replaceAll(path.sep, '/').replace(/^\/+/, '').replace(/\/+$/, '');
}

function normalizeBaseUrl(value) {
  const trimmed = trimToNull(value);
  return trimmed ? trimmed.replace(/\/+$/, '') : null;
}

function normalizeTimestamp(value) {
  const trimmed = trimToNull(value);
  if (!trimmed) {
    return null;
  }
  const date = new Date(trimmed);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function diffTimestamps(startedAt, completedAt) {
  const started = new Date(startedAt).getTime();
  const completed = new Date(completedAt).getTime();
  return Number.isFinite(started) && Number.isFinite(completed) && completed >= started
    ? completed - started
    : null;
}

function parseInteger(value) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function trimToNull(value) {
  const trimmed = String(value || '').trim();
  return trimmed || null;
}

function tryParseJson(value) {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(1);
});
