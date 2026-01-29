const summarizeStorage = (storage) => {
  const keys = Object.keys(storage);
  let sizeBytes = 0;
  keys.forEach((key) => {
    const value = storage.getItem(key);
    if (value) {
      sizeBytes += key.length + value.length;
    }
  });

  return {
    keys,
    sizeBytes
  };
};

const reportStorageUsage = () => {
  const payload = {
    localStorage: summarizeStorage(window.localStorage),
    sessionStorage: summarizeStorage(window.sessionStorage),
    documentReferrer: document.referrer || null,
    hasPasswordField: Boolean(document.querySelector("input[type='password']")),
    pageTitle: document.title
  };

  chrome.runtime.sendMessage({
    type: "storage-scan",
    payload
  });
};

if (document.readyState === "complete" || document.readyState === "interactive") {
  reportStorageUsage();
} else {
  window.addEventListener("DOMContentLoaded", reportStorageUsage, { once: true });
}
