/// <reference types="vite/client" />

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
}

interface Window {
  modelIADesktop?: ModelIADesktopBridge;
}
