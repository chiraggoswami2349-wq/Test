# Test
Test Reposatory

## Chrome Extension: Site Data Usage Inspector
This repository now includes a Chrome extension that inspects network requests, storage usage, and cookies for the active tab to surface potentially sensitive data usage.

### Load the extension locally
1. Open **Chrome** and go to `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the `chrome-extension` folder in this repository.
4. Open a site, click the extension icon, and review the report.

### What it checks
- Network requests and headers for common sensitive indicators (tokens, auth headers, cookies).
- Query string parameters that look like credentials or tokens.
- Local/session storage key counts and approximate size.
- Cookie inventory for the current site.

> Note: The extension highlights risk signals, but it cannot prove malicious intent on its own.
