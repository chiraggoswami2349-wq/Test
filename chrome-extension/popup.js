const formatBytes = (bytes) => {
  if (bytes === 0) return "0 B";
  if (!bytes) return "--";
  const units = ["B", "KB", "MB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(1)} ${units[index]}`;
};

const createListItem = (title, details, extra = "") => {
  const item = document.createElement("li");
  const strong = document.createElement("strong");
  strong.textContent = title;
  item.appendChild(strong);

  const detail = document.createElement("div");
  detail.textContent = details;
  item.appendChild(detail);

  if (extra) {
    const extraLine = document.createElement("div");
    extraLine.textContent = extra;
    item.appendChild(extraLine);
  }

  return item;
};

const renderFindings = (findings) => {
  const list = document.getElementById("findings");
  list.innerHTML = "";

  if (!findings.length) {
    list.appendChild(createListItem("No sensitive findings yet", "Keep browsing to collect more data."));
    return;
  }

  findings.slice(0, 10).forEach((entry) => {
    entry.findings.forEach((finding) => {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = finding.type;

      const item = document.createElement("li");
      const strong = document.createElement("strong");
      strong.textContent = entry.url;
      item.appendChild(strong);

      const detail = document.createElement("div");
      detail.appendChild(badge);
      detail.appendChild(document.createTextNode(`${finding.key}: ${finding.reason}`));
      item.appendChild(detail);

      if (finding.valuePreview) {
        const preview = document.createElement("div");
        preview.textContent = `Preview: ${finding.valuePreview}`;
        item.appendChild(preview);
      }

      list.appendChild(item);
    });
  });
};

const renderRequests = (requests) => {
  const list = document.getElementById("requests");
  list.innerHTML = "";

  if (!requests.length) {
    list.appendChild(createListItem("No requests logged", "Open a page to begin logging."));
    return;
  }

  requests.slice(-10).reverse().forEach((request) => {
    const title = `${request.method} ${request.type}`;
    const details = request.url;
    const extra = request.hasSensitive ? "Flagged for sensitive data" : "";
    list.appendChild(createListItem(title, details, extra));
  });
};

const renderCookies = (cookies) => {
  const cookieCount = document.getElementById("cookie-count");
  cookieCount.textContent = `${cookies.length} cookies detected`;
};

const renderStorage = (storage) => {
  const localStorageEl = document.getElementById("local-storage");
  const sessionStorageEl = document.getElementById("session-storage");

  if (!storage) {
    localStorageEl.textContent = "Local storage: --";
    sessionStorageEl.textContent = "Session storage: --";
    return;
  }

  const localSummary = `${storage.localStorage.keys.length} keys (${formatBytes(storage.localStorage.sizeBytes)})`;
  const sessionSummary = `${storage.sessionStorage.keys.length} keys (${formatBytes(storage.sessionStorage.sizeBytes)})`;

  localStorageEl.textContent = `Local storage: ${localSummary}`;
  sessionStorageEl.textContent = `Session storage: ${sessionSummary}`;
};

const loadReport = () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const tab = tabs[0];
    if (!tab || !tab.id) {
      return;
    }

    chrome.runtime.sendMessage({ type: "get-report", tabId: tab.id }, (response) => {
      const report = response?.report;
      if (!report) {
        return;
      }

      document.getElementById("request-count").textContent = `${report.requests.length} requests observed`;
      document.getElementById("sensitive-count").textContent = `${report.sensitiveFindings.length} sensitive findings`;
      renderFindings(report.sensitiveFindings);
      renderRequests(report.requests);
      renderStorage(report.storage);
    });

    chrome.runtime.sendMessage({ type: "get-cookies", tabId: tab.id, url: tab.url }, (response) => {
      renderCookies(response?.cookies || []);
    });
  });
};

document.addEventListener("DOMContentLoaded", loadReport);
