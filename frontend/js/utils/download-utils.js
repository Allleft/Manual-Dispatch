export function getExportFilename(response, fallbackFilename) {
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  return match ? match[1] : fallbackFilename;
}


export async function downloadExcelResponse(response, fallbackFilename) {
  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = getExportFilename(response, fallbackFilename);
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(downloadUrl);
}
