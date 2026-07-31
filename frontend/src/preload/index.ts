import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld(
  "modelIADesktop",
  Object.freeze({
    platform: process.platform,
    loadWorkspace: (): Promise<unknown> =>
      ipcRenderer.invoke("model-ia:workspace:load") as Promise<unknown>,
    saveWorkspace: (workspace: unknown): Promise<unknown> =>
      ipcRenderer.invoke(
        "model-ia:workspace:save",
        workspace,
      ) as Promise<unknown>,
    pickAttachments: (projectId: string): Promise<unknown> =>
      ipcRenderer.invoke(
        "model-ia:attachments:pick",
        projectId,
      ) as Promise<unknown>,
    removeAttachment: (
      projectId: string,
      storedName: string,
    ): Promise<boolean> =>
      ipcRenderer.invoke(
        "model-ia:attachments:remove",
        projectId,
        storedName,
      ) as Promise<boolean>,
    openAttachment: (
      projectId: string,
      storedName: string,
    ): Promise<boolean> =>
      ipcRenderer.invoke(
        "model-ia:attachments:open",
        projectId,
        storedName,
      ) as Promise<boolean>,
    removeProjectData: (projectId: string): Promise<boolean> =>
      ipcRenderer.invoke(
        "model-ia:projects:remove-data",
        projectId,
      ) as Promise<boolean>,
  }),
);
