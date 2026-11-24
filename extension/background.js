// TabMind Background Service

chrome.runtime.onInstalled.addListener(() => {
    console.log("TabMind extension installed successfully.");

    chrome.storage.local.set({
        tabmind_installed: true
    });
});

chrome.runtime.onStartup.addListener(() => {
    console.log("TabMind is running.");
});