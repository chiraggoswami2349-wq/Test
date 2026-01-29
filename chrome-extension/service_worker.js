const SENSITIVE_QUERY_KEYS = [
  "token",
  "auth",
  "password",
  "passwd",
  "session",
  "sid",
  "jwt",
  "key",
  "secret",
  "credential",
  "bearer"
];

const SENSITIVE_HEADERS = [
  "authorization",
  "cookie",
  "x-csrf-token",
  "x-api-key",
  "x-auth-token"
];

const tabReports = new Map();

const ensureReport = (tabId) => {
  if (!tabReports.has(tabId)) {
    tabReports.set(tabId, {
      requests: [],
      sensitiveFindings: [],
      storage: null,
      lastUpdated: Date.now()
    });
  }
  return tabReports.get(tabId);
};

const normalizeHeaderName = (name) => name.toLowerCase();

const extractSensitiveQueryParams = (url) => {
  const findings = [];
  const parsedUrl = new URL(url);
  for (const [key, value] of parsedUrl.searchParams.entries()) {
    const keyLower = key.toLowerCase();
    const match = SENSITIVE_QUERY_KEYS.find((needle) => keyLower.includes(needle));
    if (match) {
      findings.push({
        type: "query-param",
        key,
        valuePreview: value ? value.slice(0, 32) : "",
        reason: `Query param name contains "${match}"`
      });
    }
  }
  return findings;
};

const extractSensitiveHeaders = (headers = []) => {
  const findings = [];
  headers.forEach((header) => {
    const nameLower = normalizeHeaderName(header.name || "");
    if (SENSITIVE_HEADERS.includes(nameLower)) {
      findings.push({
        type: "header",
        key: header.name,
        valuePreview: header.value ? header.value.slice(0, 32) : "",
        reason: "Sensitive request header detected"
      });
    }
  });
  return findings;
};

chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {
    if (details.tabId < 0) {
      return;
    }

    const report = ensureReport(details.tabId);
    const queryFindings = extractSensitiveQueryParams(details.url);
    const headerFindings = extractSensitiveHeaders(details.requestHeaders || []);
    const findings = [...queryFindings, ...headerFindings];

    if (findings.length) {
      report.sensitiveFindings.push({
        url: details.url,
        timeStamp: details.timeStamp,
        findings
      });
    }

    report.requests.push({
      url: details.url,
      method: details.method,
      type: details.type,
      initiator: details.initiator || null,
      timeStamp: details.timeStamp,
      hasSensitive: findings.length > 0
    });

    report.lastUpdated = Date.now();
  },
  { urls: ["<all_urls>"] },
  ["requestHeaders"]
);

chrome.tabs.onRemoved.addListener((tabId) => {
  tabReports.delete(tabId);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "storage-scan" && sender.tab?.id != null) {
    const report = ensureReport(sender.tab.id);
    report.storage = message.payload;
    report.lastUpdated = Date.now();
  }

  if (message.type === "get-report") {
    const tabId = message.tabId;
    const report = ensureReport(tabId);
    sendResponse({
      report
    });
  }

  if (message.type === "get-cookies") {
    const { tabId, url } = message;
    chrome.cookies.getAll({ url }, (cookies) => {
      const cookieSummaries = cookies.map((cookie) => ({
        name: cookie.name,
        domain: cookie.domain,
        path: cookie.path,
        session: cookie.session,
        secure: cookie.secure,
        httpOnly: cookie.httpOnly
      }));

      sendResponse({ cookies: cookieSummaries });
    });

    return true;
  }

  return undefined;
});
