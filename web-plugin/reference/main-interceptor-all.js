/**
 * main-interceptor-all.js
 * 登录安全拦截一体化脚本
 *
 * 由后端 loadJavaScript 注入，并替换模板变量：
 *   ${loginApi}             - 登录接口路径
 *   ${loginField}           - 账号输入框匹配规则（key=value&key=value）
 *   ${loginButton}          - 登录按钮匹配规则（key=value&key=value 或 CSS 选择器）
 *   ${loginPagePaths}       - 登录页面路径列表
 */


/////////////////////////////////////////////////////////////////////////////////////
///////////                       message.js                       //////////////////////
/////////////////////////////////////////////////////////////////////////////////////

// message.js Global function to display error messages
function showGlobalErrorMessage(message) {
    let errorToast = document.getElementById('ym-global-error-toast');
    if (!errorToast) {
        errorToast = document.createElement('div');
        errorToast.id = 'ym-global-error-toast';
        errorToast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: #e74c3c;
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 9999;
            font-size: 14px;
            opacity: 0;
            transform: translateX(100%);
            transition: all 0.3s ease;
        `;
        document.body.appendChild(errorToast);
    } else {
        return;
    }

    // Set error message
    errorToast.textContent = message;

    // Show error message
    setTimeout(() => {
        errorToast.style.opacity = '1';
        errorToast.style.transform = 'translateX(0)';
    }, 10);

    // Hide error message after 3 seconds
    setTimeout(() => {
        if (errorToast.parentNode) {
            errorToast.parentNode.removeChild(errorToast);
        }
    }, 3000);
}


/////////////////////////////////////////////////////////////////////////////////////
///////////                      verification.js                   //////////////////////
/////////////////////////////////////////////////////////////////////////////////////

// Define PIN verification component
function createPinVerification(options = {}) {
    // Merge default options with user options
    const config = {
        correctPin: "111111",
        pinLength: 6,
        onSuccess: () => {
        },
        onFailure: () => {
        },
        autoCloseOnSuccess: true,
        ...options
    };

    /**
     * Create CSS styles for verification component
     */
    function createStyles() {
        const style = document.createElement('style');
        style.textContent = `
        .ym-demo-area {
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            padding: 30px;
            margin-bottom: 30px;
        }

        .ym-demo-content {
            text-align: center;
            padding: 20px 0;
        }

        .ym-integration {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 25px;
            margin-top: 30px;
        }

        .ym-code-block {
            background: #2c3e50;
            color: #ecf0f1;
            border-radius: 8px;
            padding: 20px;
            font-family: 'Fira Code', monospace;
            overflow-x: auto;
            margin: 20px 0;
            font-size: 15px;
            line-height: 1.6;
        }

        .ym-buttons {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 25px;
        }

        .ym-btn {
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            border: none;
            display: inline-flex;
            align-items: center;
            font-size: 16px;
        }

        .ym-btn-primary {
            background: #3498db;
            color: white;
            box-shadow: 0 4px 10px rgba(52, 152, 219, 0.3);
        }

        .ym-btn-primary:hover {
            background: #2980b9;
            transform: translateY(-2px);
        }

        .ym-btn-secondary {
            background: #ecf0f1;
            color: #2c3e50;
        }

        .ym-btn-secondary:hover {
            background: #dde4e7;
            transform: translateY(-2px);
        }

        .ym-icon {
            margin-right: 8px;
        }

        @media (max-width: 600px) {
            .ym-buttons {
                flex-direction: column;
                align-items: center;
            }

            .ym-btn {
                width: 100%;
                justify-content: center;
            }
        }

        .ym-pin-modal {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2147483647 !important;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s;
        }

        .ym-pin-modal * {
            z-index: inherit;
        }

        .ym-modal-backdrop {
            z-index: 2147483647 !important;
        }

        .ym-modal-content {
            z-index: 2147483647 !important;
        }

        .ym-modal-backdrop {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(5px);
        }

        .ym-modal-content {
            position: relative;
            background-color: white;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
            width: 100%;
            max-width: 380px;
            margin: 0 20px;
            transform: scale(0.95);
            opacity: 0;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        .ym-modal-header {
            padding: 28px 24px 20px;
            text-align: center;
        }

        .ym-modal-icon {
            width: 60px;
            height: 60px;
            background-color: rgba(52, 152, 219, 0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 16px;
            font-size: 24px;
            color: #3498db;
        }

        .ym-modal-title {
            font-size: 22px;
            font-weight: 700;
            color: #2c3e50;
            margin-bottom: 6px;
        }

        .ym-modal-subtitle {
            color: #7f8c8d;
            font-size: 15px;
            margin-bottom: 24px;
        }

        .ym-pin-dots {
            display: flex;
            justify-content: center;
            gap: 18px;
            margin-bottom: 32px;
        }

        .ym-pin-dot {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background-color: #e0e0e0;
            transition: all 0.3s ease;
        }

        .ym-pin-dot.ym-filled {
            background-color: #3498db;
            transform: scale(1.2);
        }

        .ym-error-message {
            color: #e74c3c;
            font-size: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            margin-top: -15px;
            margin-bottom: -10px;
            opacity: 0;
            transition: opacity 0.3s;
        }

        .ym-error-message.ym-show {
            opacity: 1;
        }

        .ym-keypad {
            padding: 0 24px 20px;
        }

        .ym-keypad-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin: 0 auto;
            max-width: 280px;
        }

        .ym-keypad-btn {
            height: 60px;
            border-radius: 12px;
            background-color: #f8f9fa;
            color: #2c3e50;
            font-size: 22px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            border: none;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .ym-keypad-btn:hover {
            background-color: #e9ecef;
            transform: translateY(-2px);
        }

        .ym-keypad-btn:active {
            transform: translateY(0);
            background-color: #dee2e6;
        }

        .ym-keypad-action {
            font-size: 18px;
            background-color: #f1f3f5;
        }

        .ym-modal-footer {
            padding: 16px 24px 24px;
            display: flex;
            gap: 12px;
        }

        .ym-footer-btn {
            flex: 1;
            padding: 15px;
            border-radius: 10px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            border: none;
            font-size: 16px;
        }

        .ym-footer-btn-secondary {
            background-color: #f8f9fa;
            color: #7f8c8d;
        }

        .ym-footer-btn-secondary:hover {
            background-color: #e9ecef;
        }

        .ym-footer-btn-primary {
            background-color: #3498db;
            color: white;
            opacity: 0.7;
            cursor: not-allowed;
        }

        .ym-footer-btn-primary.ym-enabled {
            opacity: 1;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3);
        }

        .ym-footer-btn-primary.ym-enabled:hover {
            background-color: #2980b9;
        }

        .ym-success-toast {
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            background-color: #27ae60;
            color: white;
            padding: 14px 28px;
            border-radius: 10px;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            gap: 10px;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s;
            z-index: 2147483647 !important;
            font-size: 16px;
            font-weight: 500;
        }

        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            10%, 30%, 50%, 70%, 90% { transform: translateX(-8px); }
            20%, 40%, 60%, 80% { transform: translateX(8px); }
        }

        .ym-shake {
            animation: shake 0.5s cubic-bezier(.36,.07,.19,.97) both;
        }
    `;
        document.head.appendChild(style);
    }

    /**
     * Create DOM elements for verification component
     *
     * @returns {Object} Object containing references to component elements
     */
    function createElements() {
        // Generate PIN dots HTML based on configured PIN length
        const pinDotsHtml = Array(config.pinLength).fill('<div class="ym-pin-dot"></div>').join('');

        const pinModal = document.createElement('div');
        pinModal.className = 'ym-pin-modal';
        pinModal.innerHTML = `
        <div class="ym-modal-backdrop"></div>
        <div class="ym-modal-content">
            <div class="ym-modal-header">
                <div class="ym-modal-icon">&#128274;</div>
                <h2 class="ym-modal-title">Enter PIN</h2>
                <p class="ym-modal-subtitle">Please enter a ${config.pinLength}-digit PIN</p>

                <div class="ym-pin-dots">
                    ${pinDotsHtml}
                </div>

                <div class="ym-error-message">
                    <span id="ym-errorMessage">✕ Invalid PIN, please try again</span>
                </div>
            </div>

            <div class="ym-keypad">
                <div class="ym-keypad-grid">
                    <button class="ym-keypad-btn" data-value="1" tabindex="0">1</button>
                    <button class="ym-keypad-btn" data-value="2" tabindex="0">2</button>
                    <button class="ym-keypad-btn" data-value="3" tabindex="0">3</button>
                    <button class="ym-keypad-btn" data-value="4" tabindex="0">4</button>
                    <button class="ym-keypad-btn" data-value="5" tabindex="0">5</button>
                    <button class="ym-keypad-btn" data-value="6" tabindex="0">6</button>
                    <button class="ym-keypad-btn" data-value="7" tabindex="0">7</button>
                    <button class="ym-keypad-btn" data-value="8" tabindex="0">8</button>
                    <button class="ym-keypad-btn" data-value="9" tabindex="0">9</button>
                    <button class="ym-keypad-btn ym-keypad-action" id="ym-clearBtn" tabindex="0">clear</button>
                    <button class="ym-keypad-btn" data-value="0" tabindex="0">0</button>
                    <button class="ym-keypad-btn ym-keypad-action" id="ym-backspaceBtn" tabindex="0">delete</button>
                </div>
            </div>

            <div class="ym-modal-footer">
                <button class="ym-footer-btn ym-footer-btn-secondary" id="ym-cancelBtn">cancel</button>
                <button class="ym-footer-btn ym-footer-btn-primary" id="ym-submitBtn" disabled>confirm</button>
            </div>
        </div>
    `;

        const successToast = document.createElement('div');
        successToast.className = 'ym-success-toast';
        successToast.innerHTML = `<span>&#9989;</span> PIN verification successful!`;

        document.body.appendChild(pinModal);
        document.body.appendChild(successToast);

        return {
            pinModal,
            modalContent: pinModal.querySelector('.ym-modal-content'),
            modalBackdrop: pinModal.querySelector('.ym-modal-backdrop'),
            cancelBtn: pinModal.querySelector('#ym-cancelBtn'),
            submitBtn: pinModal.querySelector('#ym-submitBtn'),
            digitButtons: pinModal.querySelectorAll('.ym-keypad-btn[data-value]'),
            backspaceBtn: pinModal.querySelector('#ym-backspaceBtn'),
            clearBtn: pinModal.querySelector('#ym-clearBtn'),
            pinDots: pinModal.querySelectorAll('.ym-pin-dot'),
            errorMessage: pinModal.querySelector('.ym-error-message'),
            successToast
        };
    }

    /**
     * Initialize component
     * Set up event listeners and internal state
     */
    function init() {
        createStyles();
        const elements = createElements();
        let currentPin = '';
        const pinLength = config.pinLength;

        let verifyFunc = null;

        /**
         * Find the highest z-index currently used on the page.
         * This lets us dynamically place the PIN modal above any other overlay
         * (Vue/React loaders, Element-UI messages, etc.) regardless of what
         * z-index those overlays happen to use.
         *
         * @returns {number} The highest positive z-index found among positioned elements
         */
        const getMaxZIndex = () => {
            let maxZ = 0;
            const allElements = document.querySelectorAll('*');
            for (let i = 0; i < allElements.length; i++) {
                const el = allElements[i];
                if (el === elements.pinModal || elements.pinModal.contains(el)) continue;
                const position = window.getComputedStyle(el).position;
                if (position === 'static') continue;
                const zIndex = parseInt(window.getComputedStyle(el).zIndex, 10);
                if (!isNaN(zIndex) && zIndex > maxZ) {
                    maxZ = zIndex;
                }
            }
            return maxZ;
        };

        /**
         * Open PIN verification modal
         *
         * @param {Function} func - Callback function after verification is complete
         */
        const openModal = (func) => {
            verifyFunc = func;

            // Move PIN modal to the end of body so it is last in DOM order,
            // guaranteeing it sits on top of same-z-index siblings
            if (elements.pinModal.parentNode !== document.body) {
                document.body.appendChild(elements.pinModal);
            }
            document.body.appendChild(elements.pinModal);

            // Dynamically compute a z-index higher than any element currently
            // present on the page (covers framework-level loaders, dialogs, etc.)
            const currentMaxZ = getMaxZIndex();
            const pinZ = Math.max(currentMaxZ + 10, 2147483647);
            elements.pinModal.style.zIndex = pinZ + ' !important';
            const contentEl = elements.pinModal.querySelector('.ym-modal-content');
            const backdropEl = elements.pinModal.querySelector('.ym-modal-backdrop');
            if (contentEl) contentEl.style.zIndex = pinZ + ' !important';
            if (backdropEl) backdropEl.style.zIndex = pinZ + ' !important';

            elements.pinModal.style.opacity = '1';
            elements.pinModal.style.pointerEvents = 'all';

            // Blur document to ensure other page elements lose focus
            if (document.activeElement && typeof document.activeElement.blur === 'function') {
                document.activeElement.blur();
            }

            setTimeout(() => {
                elements.modalContent.style.transform = 'scale(1)';
                elements.modalContent.style.opacity = '1';

                // Set focus to PIN modal
                elements.modalContent.setAttribute('tabindex', '-1');
                elements.modalContent.focus();

                // Add focus trapping to prevent focus escape
                const trapFocus = (e) => {
                    if (!elements.pinModal.contains(e.target)) {
                        e.preventDefault();
                        elements.modalContent.focus();
                    }
                };

                document.addEventListener('focusin', trapFocus);
                // Save the remove listener function to element for use when closing
                elements.pinModal._removeFocusTrap = () => {
                    document.removeEventListener('focusin', trapFocus);
                };
            }, 10);

            resetPin();
        };

        /**
         * Close PIN verification modal
         *
         * @param {Event} event - Event that triggered the close
         * @param {boolean} pinCheck - Whether PIN verification was completed
         */
        const closeModal = (event, pinCheck = false) => {
            if (!pinCheck) {
                verifyResult = false;
                if (verifyFunc) verifyFunc({verifyResult});
            }
            elements.modalContent.style.transform = 'scale(0.95)';
            elements.modalContent.style.opacity = '0';

            setTimeout(() => {
                elements.pinModal.style.opacity = '0';
                elements.pinModal.style.pointerEvents = 'none';

                // Restore page focus
                elements.modalContent.removeAttribute('tabindex');
                if (document.activeElement && document.activeElement !== document.body) {
                    document.activeElement.blur();
                }
            }, 300);

            resetPin();
        };

        /**
         * Reset PIN input state
         */
        const resetPin = () => {
            currentPin = '';
            updatePinDisplay();
            hideErrorMessage();
        };

        /**
         * Update PIN input display
         */
        const updatePinDisplay = () => {
            elements.pinDots.forEach((dot, index) => {
                if (index < currentPin.length) {
                    dot.classList.add('ym-filled');
                } else {
                    dot.classList.remove('ym-filled');
                }
            });

            // Update submit button state
            if (currentPin.length === pinLength) {
                elements.submitBtn.disabled = false;
                elements.submitBtn.classList.add('ym-enabled');
            } else {
                elements.submitBtn.disabled = true;
                elements.submitBtn.classList.remove('ym-enabled');
            }
        };

        /**
         * Show error message
         */
        const showErrorMessage = () => {
            elements.errorMessage.classList.add('ym-show');
            elements.modalContent.classList.add('ym-shake');
        };

        /**
         * Hide error message
         */
        const hideErrorMessage = () => {
            elements.errorMessage.classList.remove('ym-show');
        };

        /**
         * Show verification success toast
         */
        const showSuccessToast = () => {
            elements.successToast.style.opacity = '1';

            setTimeout(() => {
                elements.successToast.style.opacity = '0';
            }, 2000);
        };

        // UKEY-related information storage
        let serialNumber = '';        // UKEY serial number
        let plainText = '';           // Original random text
        let signResult = '';          // Signature result
        let verifyResult = false;     // Verification result
        let certInfo = '';            // Certificate information

        // U_KEY helper access configuration
        const ukeyHttp = "http://127.0.0.1:38080";
        const ukeyContentType = "application/x-www-form-urlencoded";

        /**
         * Validate PIN and perform signature operation
         */
        const validatePinAndSign = async () => {
            try {
                let checkPin = await verifyPinRemote(currentPin);
                if (checkPin) {
                    showSuccessToast();
                    config.onSuccess();

                    await getDeviceInfoRemote();
                    let random = await getRandom();
                    console.log("Random number obtained: " + random);
                    if (random) {
                        closeModal(null, true);
                        await signWithPinRemote();
                    } else {
                        closeModal(null, false);
                    }
                } else {
                    showErrorMessage();
                    setTimeout(resetPin, 1000);
                    config.onFailure();
                }
            } catch (error) {
                console.error('Error occurred during PIN verification:', error);
                showGlobalErrorMessage('An error occurred during verification');
                closeModal(null, false);
            }
        };

        /**
         * Send HTTP request to get server-generated random number
         *
         * @returns {Promise<boolean>} Whether random number was obtained successfully
         */
        const getRandom = async () => {
            try {
                const urlRandom = `${pinVerifier.baseUrl}/genRandom?serialNumber=${encodeURIComponent(serialNumber)}`;
                const response = await fetch(urlRandom, {method: 'GET'});
                if (!response.ok) {
                    showGlobalErrorMessage('Failed to obtain random number');
                    return false;
                }
                const data = await response.text();
                if (data) {
                    plainText = data + '';
                    return true;
                }
                return false;
            } catch (error) {
                console.error('Error:', error);
                return false;
            }
        };

        /**
         * Verify PIN remotely
         *
         * @param {string} pin - Input PIN
         * @returns {Promise<boolean>} Verification result
         */
        const verifyPinRemote = async (pin) => {
            return fetch(`${ukeyHttp}/sys/verifyPin`, {
                method: 'POST',
                headers: {'Content-Type': ukeyContentType},
                mode: 'cors',
                credentials: 'omit',
                body: new URLSearchParams({pin}).toString()
            }).then(response => {
                if (!response.ok) throw new Error('Network error');
                return response.json();
            }).then(async data => {
                if (data.code === 200) {
                    return true;
                } else {
                    document.getElementById('ym-errorMessage').textContent = data.message;
                    verifyResult = false;
                    return false;
                }
            }).catch(error => {
                verifyResult = false;
                console.error('Error:', error);
                document.getElementById('ym-errorMessage').textContent = 'UKEY device not detected';
            });
        };

        /**
         * Get UKEY device information
         *
         * @returns {Promise<string>} Device serial number
         */
        const getDeviceInfoRemote = async () => {
            return fetch(`${ukeyHttp}/sys/getDevInfo`, {
                method: 'POST',
                headers: {'Content-Type': ukeyContentType},
                mode: 'cors',
                credentials: 'omit',
            }).then(response => {
                if (!response.ok) throw new Error('Network error');
                return response.json();
            }).then(async data => {
                if (data.code === 200) {
                    serialNumber = data.SerialNumber;
                    return data.SerialNumber;
                }
            });
        };

        /**
         * Perform remote signature using PIN
         */
        const signWithPinRemote = async () => {
            return fetch(`${ukeyHttp}/sys/signwithpid`, {
                method: 'POST',
                headers: {'Content-Type': ukeyContentType},
                mode: 'cors',
                credentials: 'omit',
                body: new URLSearchParams({plainData: plainText, plainDataLen: plainText.length}).toString()
            }).then(response => {
                if (!response.ok) throw new Error('Network error');
                return response.json();
            }).then(async data => {
                if (data.code === 200) {
                    signResult = data.signData;
                    verifyResult = true;

                    if (verifyFunc) verifyFunc({
                        plainText,
                        signResult,
                        verifyResult,
                        certInfo,
                        serialNumber
                    });
                } else {
                    showGlobalErrorMessage(data.message);
                }
            }).catch(error => console.error('Error:', error));
        };

        // Bind event listeners
        elements.modalBackdrop.addEventListener('click', closeModal);
        elements.cancelBtn.addEventListener('click', closeModal);
        elements.digitButtons.forEach(button => {
            button.addEventListener('click', () => {
                if (currentPin.length < pinLength) {
                    currentPin += button.dataset.value;
                    updatePinDisplay();
                }
            });
        });
        elements.clearBtn.addEventListener('click', resetPin);
        elements.backspaceBtn.addEventListener('click', () => {
            if (currentPin.length > 0) {
                currentPin = currentPin.slice(0, -1);
                updatePinDisplay();
            }
        });
        elements.submitBtn.addEventListener('click', validatePinAndSign);

        // Keyboard support
        document.addEventListener('keydown', (e) => {
            if (elements.pinModal.style.opacity !== '1') return;

            if (e.key >= '0' && e.key <= '9' && currentPin.length < pinLength) {
                currentPin += e.key;
                updatePinDisplay();
            }

            if (e.key === 'Backspace') {
                currentPin = currentPin.slice(0, -1);
                updatePinDisplay();
            }

            if (e.key === 'Enter' && currentPin.length === pinLength) {
                validatePinAndSign();
            }

            if (e.key === 'Escape') {
                closeModal(null, false);
            }
        });

        // Return public API
        return {
            open: openModal,
            close: closeModal,
            reset: resetPin,
            setPin: (newPin) => {
                config.correctPin = newPin;
            }
        };
    }

    return init();
}


/////////////////////////////////////////////////////////////////////////////////////
///////////                         main.js                    //////////////////////
/////////////////////////////////////////////////////////////////////////////////////

// main.js Create and initialize component
console.log('PIN modal loaded');
const pinVerifier = createPinVerification({
    pinLength: 6,
    correctPin: "123456",
    onSuccess: () => {
        console.log("PIN verification successful!");
    },
    onFailure: () => {
        console.log("PIN verification failed!");
    }
});
pinVerifier.setPin("111111");
pinVerifier.baseUrl = "http://192.168.145.128:9191";


/////////////////////////////////////////////////////////////////////////////////////
///////////                      interceptor.js                //////////////////////
/////////////////////////////////////////////////////////////////////////////////////

// 配置登录API接口地址和账户字段名
const loginApi = "/api/auth/login";
const loginField = "type=text&placeholder=请输入账号";
const loginButton = "type=button&aria-disabled=false";
const loginPagePaths = ['/#/login'];

/**
 * 判断当前页面是否为登录页面
 * 所有拦截操作（fetch/XHR/表单提交/按钮点击）仅在登录页面生效
 * 支持 hash 路由：配置 "/#/login" 时，hash 一致即命中，pathname 不限制
 */
const normalizePath = (p) => (p || '').replace(/^\/+/, '').replace(/\/+$/, '');

function splitPagePath(pageUrl) {
    const idx = (pageUrl || '').indexOf('#');
    if (idx === -1) return { path: normalizePath(pageUrl), hash: '' };
    return {
        path: normalizePath(pageUrl.substring(0, idx)),
        hash: normalizePath(pageUrl.substring(idx + 1))
    };
}

function isLoginPage() {
    const currentPath = normalizePath(window.location.pathname);
    const currentHash = normalizePath(window.location.hash.replace(/^#/, ''));
    for (let i = 0; i < loginPagePaths.length; i++) {
        const config = splitPagePath(loginPagePaths[i]);
        if (config.hash) {
            if (config.hash === currentHash && (config.path === '' || config.path === currentPath)) return true;
        } else if (config.path === currentPath) {
            return true;
        }
    }
    return false;
}

/**
 * 把 key=value&key=value 格式解析成属性条件对象
 * 例："id=Logon&name=Logon" → { id: "Logon", name: "Logon" }
 */
function parseAttributeConditions(config) {
    if (!config) return null;
    const attrs = {};
    const pairs = config.split('&');
    let hasAny = false;
    for (let i = 0; i < pairs.length; i++) {
        const pair = pairs[i];
        const eqIdx = pair.indexOf('=');
        if (eqIdx === -1) continue;
        const key = pair.substring(0, eqIdx).trim();
        let value = pair.substring(eqIdx + 1).trim();
        value = value.replace(/^['"]|['"]$/g, '');
        if (key) { attrs[key] = value; hasAny = true; }
    }
    return hasAny ? attrs : null;
}

/**
 * 判断配置是否是属性格式（包含 '&' 或 '='）
 */
function isAttributeStyle(config) {
    return !!config && (config.indexOf('&') !== -1 || config.indexOf('=') !== -1);
}

const loginButtonAttrConditions = isAttributeStyle(loginButton)
    ? parseAttributeConditions(loginButton)
    : null;
const loginButtonCssSelectors = (loginButton && !loginButtonAttrConditions)
    ? loginButton.split(',').map(function (s) { return s.trim(); }).filter(Boolean)
    : [];

/**
 * 判断元素是否命中属性条件（key=value&key=value，AND 匹配）
 * 账号输入框与登录按钮共用同一套匹配逻辑
 */
function elementMatchesAttrConditions(element, conditions) {
    if (!element || !conditions) return false;
    for (var key in conditions) {
        if (!Object.prototype.hasOwnProperty.call(conditions, key)) continue;
        var expected = conditions[key];

        if (key === 'class' || key === 'className') {
            var classList = expected.split(/\s+/).filter(Boolean);
            for (var ci = 0; ci < classList.length; ci++) {
                if (element.classList) {
                    if (!element.classList.contains(classList[ci])) return false;
                } else {
                    var cls = (element.getAttribute && element.getAttribute('class')) || '';
                    if ((' ' + cls + ' ').indexOf(' ' + classList[ci] + ' ') === -1) return false;
                }
            }
            continue;
        }

        var actual = (key in element && element[key] != null)
            ? String(element[key])
            : String((element.getAttribute && element.getAttribute(key)) || '');
        if (actual !== expected) return false;
    }
    return true;
}


/**
 * 判断 URL 是否精确匹配登录接口
 *
 * 将前端传入的 URL（可能是相对路径、绝对路径、完整 URL）统一解析为完整的绝对路径，
 * 再与配置的 loginApi 做精确比较。这样既兼容前端各种写法，又保证精确匹配：
 *
 *   loginApi = "/sho/login"
 *   前端传 "login"          → 解析为当前页面路径下的 "/sho/login"    → ✅ 精确匹配
 *   前端传 "/sho/login"     → pathname = "/sho/login"             → ✅ 精确匹配
 *   前端传 "http://x.com/sho/login" → pathname = "/sho/login"     → ✅ 精确匹配
 *   前端传 "/api/admin/login" → pathname = "/api/admin/login"     → ❌ 不匹配
 */
function isLoginApiUrl(url) {
    if (!loginApi || !url) return false;

    let requestPath;
    try {
        const absoluteUrl = new URL(url, window.location.href);
        requestPath = absoluteUrl.pathname;
    } catch (e) {
        requestPath = url.split('?')[0];
    }

    // 精确匹配
    const normalize = (p) => p.replace(/^\/+/, '').replace(/\/+$/, '');
    return normalize(requestPath) === normalize(loginApi);
}

console.log("%c[Login-Interceptor] 配置加载完成", "color:#1E90FF;font-weight:bold;");
console.log("  loginApi:", loginApi);
console.log("  loginField:", loginField);
console.log("  loginButton:", loginButton);

/**
 * 从DOM输入框中获取未加密的原始账号
 *
 * loginField 格式示例：
 *   id=USERNAME
 *   placeholder='手机号/身份证'&type='text'&class='el-input__inner'
 *
 * @param {Element|Document} [scope=document] - 查找范围，拦截时优先传入按钮/表单本身
 * @returns {string|null} 输入框的原始值，未找到则返回 null
 */
function extractUsernameFromInput(scope) {
    const conditions = parseAttributeConditions(loginField);
    if (!conditions) {
        return null;
    }

    // 先在被限定的作用域内查找（如登录按钮所在表单），未命中再回退到整个文档
    const roots = [];
    if (scope && scope.querySelectorAll && scope !== document) {
        roots.push(scope);
    }
    roots.push(document);

    for (let r = 0; r < roots.length; r++) {
        const inputs = roots[r].querySelectorAll('input');
        for (let i = 0; i < inputs.length; i++) {
            const input = inputs[i];
            if (!elementMatchesAttrConditions(input, conditions)) continue;

            if (input.value && input.value.trim()) {
                console.log("[DOM] ✅ 从输入框获取原始账号: %s", input.value.trim());
                return input.value.trim();
            }
        }
    }

    return null;
}

/**
 * 验证登录账号是否需要使用UKey登录
 *
 * @param {string} username - 用户名
 * @returns {Promise<boolean>} 是否需要PIN验证
 */
async function handleVerifyUser(username) {
    const verifyUrl = `${pinVerifier.baseUrl}/verifyUser?username=${encodeURIComponent(username)}`;

    try {
        const response = await fetch(verifyUrl, { method: 'GET' });
        if (response.ok) {
            return await response.json();
        } else {
            console.warn('User verification service response abnormal, skipping PIN verification');
        }
    } catch (error) {
        console.error('User verification request failed:', error);
        // throw new Error('签名验证');
    }

    return false;
}

/**
 * 执行签名验证
 *
 * @param {Object} data - 包含签名信息的数据对象
 * @param {string} data.plainText - 原文
 * @param {string} data.signResult - 签名结果
 * @param {string} data.serialNumber - 设备序列号
 * @param {string} data.username - 用户名
 * @returns {Promise<Object>} 验证结果
 */
function handleVerifySign(data) {
    // 首先检查本地验证结果
    if (!data.verifyResult) {
        console.log('Local verification failed, aborting request');
        throw new Error('Signature verification failed');
    }

    // 构建签名验证请求参数
    const verifyUrl = `${pinVerifier.baseUrl}/verifySign`;
    const requestBody = {
        plainText: data.plainText,
        signResult: data.signResult,
        originalText: data.plainText,
        signature: data.signResult,
        serialNumber: data.serialNumber,
        username: data.username
    };

    // 发送签名验证请求
    return fetch(verifyUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
    })
        .then(verifyResponse => {
            if (verifyResponse.ok) {
                return verifyResponse.text();
            } else {
                console.error('Signature verification request failed, aborting');
                throw new Error('Signature verification failed');
            }
        })
        .then(verifyResult => {
            if (verifyResult !== 'true') {
                console.error('Server signature verification failed, aborting');
                throw new Error('Signature verification failed');
            }

            console.log('Signature verification successful, proceeding');
            return { success: true };
        });
}


/////////////////////////////////////////////////////////////////////////////////////
///////////                      拦截fetch请求                   //////////////////////
/////////////////////////////////////////////////////////////////////////////////////

/**
 * 拦截fetch请求以实现登录验证功能
 * 对于登录请求，先检查是否需要PIN验证，再决定是否放行
 */
const originalFetch = window.fetch;
window.fetch = async (...args) => {
    const [input, options = {}] = args;
    const url = typeof input === 'string' ? input : input.url;
    // 非登录页面不拦截
    if (!isLoginPage()) {
        return originalFetch(...args);
    }
    const isLoginApi = isLoginApiUrl(url);

    console.log("[Fetch] 请求拦截: url=%s, loginApi=%s, 匹配=%s", url, loginApi, isLoginApi);

    if (window._pinVerifying && isLoginApi) {
        console.warn('PIN verifying: fetch login request blocked');
        throw new Error('PIN verification in progress, please complete verification first');
    }

    if (!isLoginApi) {
        return originalFetch(...args);
    }

    // 已通过 PIN 验证（由点击拦截放行）：直接发送登录请求，避免重复弹窗
    if (window._pinVerifiedForLogin) {
        console.log("[Fetch] 已通过 PIN 验证，放行登录请求");
        return originalFetch(...args);
    }

    console.log("[Fetch] ✅ 捕获到登录请求, 开始处理...");
    const usernameValue = extractUsernameFromInput();
    if (!usernameValue) {
        console.info('Fetch request: login account not found, skipping PIN verification');
        return originalFetch(...args);
    }

    const needs = await handleVerifyUser(usernameValue);
    if (!needs) {
        console.info('Fetch request: PIN verification skipped, sending login request directly');
        return originalFetch(...args);
    }

    return new Promise((resolve, reject) => {
        pinVerifier.open(async (data) => {
            try {
                // 用户取消/ESC 关闭弹窗：直接放弃，不触发签名错误
                if (!data.verifyResult) return;
                data.username = usernameValue;
                const result = await handleVerifySign(data);
                if (result.success) {
                    const response = originalFetch(url, options);
                    resolve(response);
                }
            } catch (error) {
                console.error('Fetch request: error occurred during signature verification:', error);
                showGlobalErrorMessage('Signature verification failed');
                reject(new Error('Signature verification failed'));
            }
        });
    });
};


/////////////////////////////////////////////////////////////////////////////////////
///////////               拦截XMLHttpRequest请求                //////////////////////
/////////////////////////////////////////////////////////////////////////////////////

/**
 * 拦截XMLHttpRequest请求以实现登录验证功能
 * 重写open和send方法，对登录请求进行特殊处理
 */
const originalOpen = XMLHttpRequest.prototype.open;
const originalSend = XMLHttpRequest.prototype.send;

// 重写open方法以保存URL信息
XMLHttpRequest.prototype.open = function (method, url) {
    this._url = url;
    return originalOpen.apply(this, arguments);
};

// 重写send方法以实现请求拦截
XMLHttpRequest.prototype.send = async function (body) {
    const url = this._url || '';
    // 非登录页面不拦截
    if (!isLoginPage()) {
        return originalSend.call(this, body);
    }
    const isLoginApi = isLoginApiUrl(url);

    console.log("[XHR] 请求拦截: url=%s, loginApi=%s, 匹配=%s", url, loginApi, isLoginApi);

    if (window._pinVerifying && isLoginApi) {
        console.warn('PIN verifying: XHR login request blocked');
        return;
    }

    if (!isLoginApi) {
        return originalSend.call(this, body);
    }

    // 已通过 PIN 验证（由点击拦截放行）：直接发送登录请求，避免重复弹窗
    if (window._pinVerifiedForLogin) {
        console.log("[XHR] 已通过 PIN 验证，放行登录请求");
        return originalSend.call(this, body);
    }

    console.log("[XHR] ✅ 捕获到登录请求, 开始处理...");

    const xhr = this;
    const usernameValue = extractUsernameFromInput();
    if (!usernameValue) {
        console.info('XHR request: login account not found, skipping PIN verification');
        return originalSend.call(xhr, body);
    }

    // 获取用户数据，判断是否需要验证PIN
    const needs = await handleVerifyUser(usernameValue);
    if (!needs) {
        console.info('XHR request: PIN verification skipped, sending login request directly');
        originalSend.call(xhr, body);
        return;
    }

    // 打开PIN验证窗口
    pinVerifier.open(async (data) => {
        try {
            // 用户取消/ESC 关闭弹窗：直接放弃，不触发签名错误
            if (!data.verifyResult) return;
            data.username = usernameValue;
            const result = await handleVerifySign(data);
            if (result.success) {
                originalSend.call(xhr, body);
            }
        } catch (error) {
            console.error('XHR signature verification error:', error);
            showGlobalErrorMessage('Signature verification failed');

            // 设置错误响应状态，模拟错误响应
            xhr.dispatchEvent(new Event('loadstart'));
            xhr.dispatchEvent(new Event('load'));
            xhr.dispatchEvent(new Event('loadend'));
        }
    });
};


/////////////////////////////////////////////////////////////////////////////////////
///////////                     拦截表单提交                     //////////////////////
/////////////////////////////////////////////////////////////////////////////////////

/**
 * 判断表单是否提交到登录接口
 * 兼容 action 为空、相对路径、绝对路径等写法：
 *   <form action="">                   → 提交到当前页面
 *   <form action="dhc.logon.csp">      → 相对当前页面解析
 *   <form action="/imedical/web/xxx">  → 直接使用
 */
function isLoginForm(form) {
    if (!form) return false;
    return isLoginApiUrl(form.action || window.location.href);
}

// 区分"选择科室"提交与"登录"提交：只有登录按钮触发的提交才进行 PIN 验签
let loginSubmitTriggered = false;

const originalFormSubmit = HTMLFormElement.prototype.submit;

/**
 * 劫持原生 form.submit()
 * CSP 等老式系统常用 form.submit() 提交整个页面，该方法不会触发 submit 事件，
 * 只能通过重写原型方法来拦截。
 * 仅当本次提交由登录按钮触发（loginSubmitTriggered）时才拦截，
 * 选择科室等其他提交直接放行，避免弹 PIN。
 */
HTMLFormElement.prototype.submit = function () {
    // 非登录页面，或非登录按钮触发的提交：直接放行
    if (!isLoginPage() || window._pinVerifiedForLogin || !isLoginForm(this) || !loginSubmitTriggered) {
        return originalFormSubmit.call(this);
    }
    console.log('[Form] 捕获到登录提交: action="%s" method="%s"',
        this.action || '(空)', (this.method || '').toUpperCase());
    loginSubmitTriggered = false;
    interceptFormSubmit(this);
};

/**
 * 表单提交拦截处理：先完成 PIN 验证，再放行提交
 * 注意：form.submit() 不会触发 submit 事件，因此放行时不会再次进入拦截
 */
function interceptFormSubmit(form) {
    const usernameValue = extractUsernameFromInput(form);
    if (!usernameValue) {
        console.info('Form submission: login account not found, skipping PIN verification');
        originalFormSubmit.call(form);
        return;
    }

    handleVerifyUser(usernameValue).then((needs) => {
        if (!needs) {
            console.info('Form submission: PIN verification skipped, sending login request directly');
            originalFormSubmit.call(form);
            return;
        }

        pinVerifier.open(async (data) => {
            try {
                // 用户取消/ESC 关闭弹窗：直接放弃，不触发签名错误
                if (!data.verifyResult) return;
                data.username = usernameValue;
                const result = await handleVerifySign(data);
                if (result.success) {
                    window._pinVerifiedForLogin = true;
                    setTimeout(() => { window._pinVerifiedForLogin = false; }, 5000);
                    originalFormSubmit.call(form);
                }
            } catch (error) {
                console.error('Form signature verification error:', error);
                showGlobalErrorMessage('Signature verification failed');
                pinVerifier.close(null, false);
            }
        });
    }).catch((err) => {
        console.error('Form submission: handleVerifyUser failed', err);
        originalFormSubmit.call(form);
    });
}

// 捕获阶段委托监听所有表单提交（兼容动态创建的表单与空 action 的同路径登录）
document.addEventListener('submit', function (e) {
    if (!isLoginPage() || window._pinVerifiedForLogin) return;
    // 仅拦截由登录按钮触发的提交（选择科室等其他提交直接放行）
    if (!loginSubmitTriggered) return;
    const form = e.target;
    if (!form || !isLoginForm(form)) {
        if (form) {
            console.log('[Submit] 未命中登录表单: action="%s" method="%s" target="%s"',
                form.action || '(空)', (form.method || '').toUpperCase(), form.target || '(自身)');
        }
        return;
    }
    e.preventDefault();
    loginSubmitTriggered = false;
    interceptFormSubmit(form);
}, true);


/////////////////////////////////////////////////////////////////////////////////////
///////////                     拦截登录按钮点击                 //////////////////////
/////////////////////////////////////////////////////////////////////////////////////

/**
 * 判断元素是否为登录按钮
 * 只使用平台规则 login_button 配置匹配，不做启发式猜测：
 *   1. key=value&key=value 属性 AND 匹配（如 id=Logon&name=Logon）
 *   2. CSS 选择器逗号分隔 OR 匹配（如 #Logon, .btn-login）
 * 未配置规则时不拦截按钮点击，登录请求由 fetch/XHR/表单提交拦截兜底
 */
function elementMatchesAnyCssSelector(element, selectors) {
    if (!selectors || selectors.length === 0) return false;
    for (var i = 0; i < selectors.length; i++) {
        var sel = selectors[i];
        if (!sel) continue;
        try {
            if (element.matches && element.matches(sel)) return true;
        } catch (e) { /* 非法选择器跳过 */ }
    }
    return false;
}

function isLoginButton(element) {
    if (!element || !element.tagName) return false;

    // 1. 属性格式 AND 匹配（id=Logon&name=Logon）
    if (loginButtonAttrConditions && elementMatchesAttrConditions(element, loginButtonAttrConditions)) {
        return true;
    }

    // 2. CSS 选择器 OR 匹配（#Logon, .btn-login）
    return elementMatchesAnyCssSelector(element, loginButtonCssSelectors);
}

/**
 * 重放被拦截的点击，并临时免除后续拦截
 */
function replayLoginClick(button) {
    window._pinVerifiedForLogin = true;
    setTimeout(() => { window._pinVerifiedForLogin = false; }, 5000);
    button._pinVerified = true;
    try {
        button.click();
    } finally {
        button._pinVerified = false;
    }
}

/**
 * 获取登录账号的 DOM 查找范围：优先按钮所属表单，其次整个文档
 */
function getButtonScope(button) {
    if (button.form) return button.form;
    const form = button.closest && button.closest('form');
    return form || document;
}

/**
 * 登录按钮点击拦截：先完成 PIN 验证，再重放点击
 */
function interceptLoginButtonClick(button) {
    const usernameValue = extractUsernameFromInput(getButtonScope(button));
    if (!usernameValue) {
        console.info('Click intercept: login account not found, skipping PIN verification');
        replayLoginClick(button);
        return;
    }

    handleVerifyUser(usernameValue).then((needs) => {
        if (!needs) {
            console.info('Click intercept: PIN verification not required, allowing click');
            replayLoginClick(button);
            return;
        }

        pinVerifier.open(async (data) => {
            try {
                // 用户取消/ESC 关闭弹窗：直接放弃，不触发签名错误
                if (!data.verifyResult) return;
                data.username = usernameValue;
                const result = await handleVerifySign(data);
                if (result.success) {
                    replayLoginClick(button);
                }
            } catch (error) {
                console.error('Click intercept: signature verification failed', error);
                showGlobalErrorMessage('Signature verification failed');
                pinVerifier.close(null, false);
            }
        });
    }).catch((err) => {
        console.error('Click intercept: handleVerifyUser failed', err);
        replayLoginClick(button);
    });
}

// 捕获阶段拦截登录按钮点击，覆盖 form.submit() 等不触发 submit 事件的老式提交方式
document.addEventListener('click', function (e) {
    // 非登录页面不拦截
    if (!isLoginPage() || window._pinVerifiedForLogin) return;

    let target = e.target;
    while (target && target !== document) {
        if (target._pinVerified) return;
        if (isLoginButton(target)) {
            // 标记本次提交由登录按钮触发，表单提交拦截才会执行 PIN 验签
            loginSubmitTriggered = true;
            e.preventDefault();
            e.stopPropagation();
            interceptLoginButtonClick(target);
            return;
        }
        target = target.parentNode;
    }

    // 未命中登录按钮时输出点击目标信息，便于核对规则配置与实际元素是否一致
    const clicked = e.target;
    if (clicked && clicked.tagName) {
        console.log('[Click] 未命中登录按钮: <%s> id="%s" name="%s" type="%s" class="%s" text="%s"',
            clicked.tagName.toLowerCase(),
            clicked.id || '',
            clicked.getAttribute('name') || '',
            clicked.getAttribute('type') || '',
            (typeof clicked.className === 'string' ? clicked.className : ''),
            (clicked.textContent || '').trim().substring(0, 30));
    }
}, true);
