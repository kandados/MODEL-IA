/// <reference types="vite/client" />

interface DesktopExportFile {
  fileName: string;
  downloadUrl: string;
}

interface DesktopExportSaveResult {
  canceled: boolean;
  savedFileNames: string[];
}

interface ModelIADesktopBridge {
  platform: string;
  loadWorkspace: () => Promise<unknown>;
  saveWorkspace: (workspace: unknown) => Promise<unknown>;
  pickAttachments: (projectId: string) => Promise<unknown>;
  removeAttachment: (
    projectId: string,
    storedName: string,
  ) => Promise<boolean>;
  openAttachment: (
    projectId: string,
    storedName: string,
  ) => Promise<boolean>;
  removeProjectData: (projectId: string) => Promise<boolean>;
  saveExportFiles: (
    files: DesktopExportFile[],
  ) => Promise<DesktopExportSaveResult>;
}

interface Window {
  modelIADesktop?: ModelIADesktopBridge;
}
