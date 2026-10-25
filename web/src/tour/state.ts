// Mutable status shared by the tour's before-hooks, loader and tooltip (outside React render for simplicity).
export const tourStatus: {
  message: string; detail: string;
  exit?: () => void; restart?: () => void;
} = { message: "", detail: "" };

export const setLoading = (message: string, detail = "") => { tourStatus.message = message; tourStatus.detail = detail; };
