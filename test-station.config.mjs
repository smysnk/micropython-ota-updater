import path from 'node:path';

const rootDir = import.meta.dirname;
const python = process.env.PYTHON || 'python3';

export default {
  schemaVersion: '1',
  project: {
    name: 'micropython-ota-updater',
    rootDir,
    outputDir: path.join(rootDir, 'artifacts', 'test-station'),
    rawDir: path.join(rootDir, 'artifacts', 'test-station', 'raw'),
  },
  workspaceDiscovery: {
    provider: 'explicit',
    packages: ['python'],
  },
  execution: {
    dryRun: false,
    continueOnError: true,
    defaultCoverage: false,
  },
  render: {
    html: true,
    console: true,
    defaultView: 'module',
    includeDetailedAnalysisToggle: true,
  },
  suites: [
    {
      id: 'pytest',
      label: 'Python Unit Tests',
      adapter: 'shell',
      package: 'python',
      cwd: rootDir,
      command: [python, './scripts/test_station_pytest.py'],
      resultFormat: 'suite-json-v1',
      diagnostics: {
        label: 'Verbose pytest rerun',
        command: [python, '-m', 'pytest', '-vv'],
        timeoutMs: 120000,
      },
      coverage: {
        enabled: false,
      },
    },
  ],
  adapters: [],
};
