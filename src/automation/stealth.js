# automation/stealth.js
# 复用 get_jobs 的反检测脚本，来自原项目的 src/main/resources/stealth.min.js
# 如果本地不存在会从网络加载
STEALTH_JS = """
(function() {
    'use strict';

    // Remove webdriver property
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
    });

    // Remove chrome runtime flags
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Function;

    // Set chrome runtime
    window.navigator.chrome = { runtime: {} };

    // Mock plugins
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3],
        configurable: true
    });

    // Mock languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en-US', 'en'],
        configurable: true
    });

    // Mock hardware concurrency
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8,
        configurable: true
    });

    // Mock device memory
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8,
        configurable: true
    });

    // Remove automation flags
    const removeAutomation = () => {
        if (window.callPhantom || window._phantom) delete window.callPhantom;
        if (window.callPhantom || window._phantom) delete window._phantom;
        if (window.__webdriver_script_fn) delete window.__webdriver_script_fn;
    };
    removeAutomation();

    // WebGL vendor check bypass
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) {
            return 'Intel Inc.';
        }
        if (parameter === 37446) {
            return 'Intel Iris OpenGL Engine';
        }
        return getParameter.call(this, parameter);
    };

    // Notification permission
    if (Notification && Notification.permission === 'denied') {
        Object.defineProperty(Notification, 'permission', {
            get: () => 'default',
            configurable: true
        });
    }
})();
"""