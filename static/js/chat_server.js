/**
 * Complaint Chat - Frontend JavaScript
 * Modern UI with Tailwind styling
 */

class ComplaintChat {
    constructor() {
        this.messagesContainer = document.getElementById('chat-messages');
        this.optionsContainer = document.getElementById('options-container');
        this.inputArea = document.getElementById('input-area');
        this.messageInput = document.getElementById('message-input');
        this.sendBtn = document.getElementById('send-btn');
        this.backBtn = document.getElementById('back-btn');
        this.restartBtn = document.getElementById('restart-btn');
        this.typingIndicator = document.getElementById('typing-indicator');
        this.charCount = document.getElementById('char-count');
        this.toastContainer = document.getElementById('toast-container');
        this.progressContainer = document.getElementById('progress-container');
        this.progressBar = document.getElementById('progress-bar');
        this.progressStep = document.getElementById('progress-step');
        this.progressLabel = document.getElementById('progress-label');

        this.isLoading = false;
        this.currentInputType = 'options';
        this.selectedOptions = new Set();
        this.stepCount = 0;

        // Payment state
        this.isPaid = false;
        this.tariffLevel = 'free'; // free / standard / premium
        this.paymentPollingInterval = null;

        // Autocomplete instance
        this.currentAutocomplete = null;
        this.selectedCompanyData = null;

        this.init();
    }

    init() {
        this.bindEvents();
        this.checkInitialPaymentStatus();
        this.loadState();
        this.applyChatProtection();
    }

    /**
     * Permanent copy/selection protection on the entire chat.
     * Blocks: copy, cut, selectstart, contextmenu, dragstart, Ctrl+C/A/X
     */
    applyChatProtection() {
        // CSS: disable text selection on the chat container
        this.messagesContainer.style.userSelect = 'none';
        this.messagesContainer.style.webkitUserSelect = 'none';

        // Block copy/cut
        document.addEventListener('copy', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            e.preventDefault();
        }, true);
        document.addEventListener('cut', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            e.preventDefault();
        }, true);

        // Block text selection (except in inputs)
        document.addEventListener('selectstart', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            if (this.messagesContainer.contains(e.target) || this.optionsContainer.contains(e.target)) {
                e.preventDefault();
            }
        }, true);

        // Block right-click context menu in chat
        document.addEventListener('contextmenu', (e) => {
            if (this.messagesContainer.contains(e.target) || this.optionsContainer.contains(e.target)) {
                e.preventDefault();
            }
        }, true);

        // Block drag-select
        document.addEventListener('dragstart', (e) => {
            if (this.messagesContainer.contains(e.target) || this.optionsContainer.contains(e.target)) {
                e.preventDefault();
            }
        }, true);

        // Block Ctrl+C / Ctrl+A / Ctrl+X (except in inputs)
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            if ((e.ctrlKey || e.metaKey) && ['c', 'a', 'x'].includes(e.key.toLowerCase())) {
                e.preventDefault();
            }
        }, true);
    }

    async checkInitialPaymentStatus() {
        try {
            const response = await fetch(this.getApiEndpoint('/payment/status'));
            const data = await response.json();
            this.tariffLevel = data.tariff_level || 'free';
            if (data.paid) {
                this.isPaid = true;
            }
        } catch (e) {
            // Payment status unknown, default to unpaid
        }
    }

    bindEvents() {
        // Send button
        this.sendBtn.addEventListener('click', () => this.sendMessage());

        // Enter to send (Shift+Enter for new line)
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.updateCharCount();
            this.autoResizeTextarea();
            this.updateSendButton();
        });

        // Back button
        this.backBtn.addEventListener('click', () => this.goBack());

        // Restart button
        this.restartBtn.addEventListener('click', () => this.restart());

        // Copy protection on protected content
        document.addEventListener('copy', (e) => {
            if (document.querySelector('.paywall-protected')) {
                const sel = window.getSelection();
                const protEl = document.querySelector('.paywall-protected');
                if (protEl && protEl.contains(sel.anchorNode)) {
                    e.preventDefault();
                    this.showToast('Оплатите тариф для копирования текста жалобы', 'error');
                }
            }
        });

        // Context menu protection
        document.addEventListener('contextmenu', (e) => {
            if (e.target.closest('.paywall-protected')) {
                e.preventDefault();
                this.showToast('Оплатите тариф для работы с текстом', 'error');
            }
        });
    }

    /**
     * Get API endpoint (always uses /api/ prefix)
     */
    getApiEndpoint(path) {
        return `/api${path}`;
    }

    async loadState() {
        try {
            const endpoint = this.getApiEndpoint('/state');
            const response = await fetch(endpoint);
            const data = await response.json();

            // Clear existing messages
            this.messagesContainer.innerHTML = '';

            // Render history
            data.history.forEach(msg => {
                this.renderMessage(msg.role, msg.content, false);
            });

            // Update step count for progress
            this.stepCount = Math.floor(data.history.length / 2);
            this.updateProgress();

            // Get last assistant message for options
            const lastAssistant = [...data.history].reverse().find(m => m.role === 'assistant');
            if (lastAssistant) {
                const inputType = lastAssistant.input_type || 'options';
                if (inputType === 'sending_results' && data.data) {
                    // Restore sending results with complaint text
                    this.showInputArea(inputType, lastAssistant.options, '', {
                        results: data.data.sending_results,
                        complaint_text: data.data.complaint_text
                    });
                } else {
                    this.showInputArea(inputType, lastAssistant.options);
                }
            }

            // Show back button if we have history
            this.updateBackButton(data.history.length > 2);

            // Apply copy protection on complaint text in history for free users
            if (!this.isPaid && data.history.some(m => m.role === 'assistant' && m.content && m.content.length > 500)) {
                this.applyCopyProtection();
            }

            this.scrollToBottom();
        } catch (error) {
            console.error('Failed to load state:', error);
            this.showToast('Ошибка загрузки. Обновите страницу.', 'error');
        }
    }

    async sendMessage(message = null, displayText = null) {
        if (this.isLoading) return;

        const text = message || this.messageInput.value.trim();
        if (!text) return;

        this.isLoading = true;
        this.messageInput.value = '';
        // Clear password masking after send
        const isPassword = this.messageInput.getAttribute('data-password') === 'true';
        this.messageInput.removeAttribute('data-password');
        this.messageInput.style.webkitTextSecurity = '';
        this.updateCharCount();
        this.updateSendButton();

        // Show user message - mask if it was a password input
        const textToShow = isPassword ? '••••••' : (displayText || text);
        this.renderMessage('user', textToShow);

        // Hide options
        this.optionsContainer.classList.add('hidden');

        // Show typing indicator
        this.showTyping(true);

        // Prepare request body - always send the actual message (ID) to backend
        const requestBody = { message: text };

        // Send display text separately so backend stores readable text in history
        if (displayText && displayText !== text) {
            requestBody.display_text = displayText;
        }

        // Include company data if selected via autocomplete
        if (this.selectedCompanyData) {
            requestBody.company_data = this.selectedCompanyData;
            this.selectedCompanyData = null;
        }

        try {
            const endpoint = this.getApiEndpoint('/chat');
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });

            if (response.status === 429) {
                throw new Error('Слишком много запросов. Подождите немного.');
            }

            if (!response.ok) {
                throw new Error('Ошибка сервера');
            }

            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            // Hide typing indicator
            this.showTyping(false);

            // Update header if user just registered/logged in
            if (data.user_name) {
                this.updateUserHeader(data.user_name);
            }

            // Show assistant response
            this.renderMessage('assistant', data.message);

            // Update step count
            this.stepCount++;
            this.updateProgress();

            // Update input area - pass extra data for sending_results and target suggestions
            this.showInputArea(
                data.input_type || 'options',
                data.options,
                data.current_text,
                {
                    results: data.results,
                    pdfDownloadUrl: data.pdf_download_url,
                    targetSuggestions: data.target_suggestions
                }
            );

            // Update back button
            this.updateBackButton(data.can_go_back !== false);

        } catch (error) {
            this.showTyping(false);
            this.showToast(error.message, 'error');
        } finally {
            this.isLoading = false;
            this.scrollToBottom();
        }
    }

    renderMessage(role, content, animate = true) {
        const messageDiv = document.createElement('div');

        if (role === 'assistant') {
            messageDiv.className = `flex items-start gap-2.5 max-w-[88%] ${animate ? 'animate-fade-in' : ''}`;
            messageDiv.innerHTML = `
                <div class="w-7 h-7 rounded-md bg-primary shrink-0 flex items-center justify-center">
                    <span class="material-icons-round text-white text-xs">balance</span>
                </div>
                <div class="flex flex-col gap-0.5">
                    <div class="bg-white dark:bg-surface-lighter px-3.5 py-2.5 rounded-lg shadow-soft border border-slate-200 dark:border-white/[0.06]">
                        <div class="text-[13.5px] leading-relaxed text-slate-600 dark:text-slate-300">${this.formatMessage(content)}</div>
                    </div>
                </div>
            `;
        } else {
            messageDiv.className = `flex items-start gap-2.5 max-w-[88%] ml-auto flex-row-reverse ${animate ? 'animate-fade-in' : ''}`;
            messageDiv.innerHTML = `
                <div class="flex flex-col gap-0.5 items-end">
                    <div class="bg-primary text-white px-3.5 py-2.5 rounded-lg">
                        <div class="text-[13.5px] leading-relaxed">${this.formatMessage(content)}</div>
                    </div>
                </div>
            `;
        }

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatMessage(text) {
        // Bold text with **
        text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // Italic text with _
        text = text.replace(/_(.+?)_/g, '<em>$1</em>');

        // Code blocks with ```
        text = text.replace(/```([\s\S]+?)```/g, '<pre class="bg-slate-800 p-3 rounded-lg mt-2 mb-2 overflow-x-auto"><code>$1</code></pre>');

        // Inline code with `
        text = text.replace(/`([^`]+)`/g, '<code class="bg-slate-700 px-1 rounded">$1</code>');

        // Links
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="text-primary underline">$1</a>');

        // Line breaks
        text = text.replace(/\n/g, '<br>');

        return text;
    }

    showInputArea(type, options = null, currentText = '', extraData = {}) {
        this.currentInputType = type;
        this.selectedOptions.clear();

        // Clean up previous autocomplete
        if (this.currentAutocomplete) {
            this.currentAutocomplete.destroy();
            this.currentAutocomplete = null;
        }
        this.selectedCompanyData = null;

        // Hide options container
        this.optionsContainer.classList.add('hidden');
        this.optionsContainer.innerHTML = '';


        if ((type === 'options' || type === 'preview') && options && options.length > 0) {
            // Complaint text visible but copy-protected for free users
            if (type === 'preview' && !this.isPaid) {
                this.applyCopyProtection();
            }
            this.renderOptions(options);
            this.optionsContainer.classList.remove('hidden');
            // Also show text input for custom answers
            this.messageInput.value = currentText || '';
            this.messageInput.placeholder = 'Знаете точнее — напишите здесь...';
            this.autoResizeTextarea();
            this.updateCharCount();
            this.updateSendButton();
        } else if (type === 'multiselect' && options && options.length > 0) {
            this.renderMultiselect(options);
            this.optionsContainer.classList.remove('hidden');
        } else if (type === 'textarea' || type === 'text' || type === 'password') {
            this.messageInput.value = currentText || '';
            const placeholders = {
                'textarea': 'Опишите подробно...',
                'text': 'Введите ответ...',
                'password': 'Введите пароль...'
            };
            this.messageInput.placeholder = placeholders[type] || 'Введите ответ...';
            if (type === 'password') {
                this.messageInput.setAttribute('data-password', 'true');
                this.messageInput.style.webkitTextSecurity = 'disc';
            } else {
                this.messageInput.removeAttribute('data-password');
                this.messageInput.style.webkitTextSecurity = '';
            }
            this.autoResizeTextarea();
            this.updateCharCount();
            this.updateSendButton();
            this.messageInput.focus();
        } else if (type.startsWith('autocomplete_')) {
            // Autocomplete input types
            const acType = type.replace('autocomplete_', '');
            const placeholders = {
                'company': 'ИНН, название или опишите своими словами...',
                'address': 'Начните вводить адрес...',
                'fio': 'Введите ФИО...'
            };

            this.messageInput.value = currentText || '';
            this.messageInput.placeholder = placeholders[acType] || 'Введите...';
            this.autoResizeTextarea();
            this.updateCharCount();
            this.updateSendButton();

            // Show indicator — company allows free text, others require selection
            const labels = {
                'company': 'Найдите организацию в списке или опишите своими словами',
                'address': 'Выберите адрес из подсказок',
                'fio': 'Выберите ФИО из подсказок'
            };

            const indicator = document.createElement('div');
            indicator.id = 'autocomplete-indicator';
            indicator.className = 'autocomplete-required';
            indicator.innerHTML = `
                <span class="material-symbols-outlined">info</span>
                <span>${labels[acType] || 'Выберите из списка'}</span>
            `;
            this.optionsContainer.innerHTML = '';
            this.optionsContainer.appendChild(indicator);
            this.optionsContainer.classList.remove('hidden');

            // Company: allow free text (no mandatory selection)
            // Address/FIO: require selection from autocomplete
            this.requiresAutocompleteSelection = (acType !== 'company');
            this.autocompleteType = acType;

            // Initialize autocomplete
            this.currentAutocomplete = new Autocomplete(
                this.messageInput,
                acType,
                (item) => this.onAutocompleteSelect(item, acType)
            );

            this.messageInput.focus();
        } else if (type === 'target_suggestions' && extraData && extraData.targetSuggestions) {
            // Render Perplexity target suggestions as selectable cards
            this.renderTargetSuggestions(extraData.targetSuggestions);
        } else if (type === 'sending_results' && extraData) {
            // Render results — channels/PDF gated by tariff level
            this.currentComplaintText = extraData.complaint_text || '';
            // Copy-protect complaint text for free users
            if (!this.isPaid) {
                this.applyCopyProtection();
            }
            this.renderSendingResults(extraData.results, this.isPaid);
            this.optionsContainer.classList.remove('hidden');
        } else {
            this.requiresAutocompleteSelection = false;
        }
    }

    renderSendingResults(results, isPaid = true) {
        const container = document.createElement('div');
        container.className = 'space-y-2 max-h-[60vh] overflow-y-auto pr-1';

        // Show payment banner if not paid
        if (!isPaid) {
            const banner = document.createElement('div');
            banner.className = 'p-3 mb-1 rounded-lg bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border border-amber-200 dark:border-amber-800';
            banner.innerHTML = `
                <div class="flex items-start gap-2">
                    <span class="material-symbols-outlined text-lg text-amber-500 shrink-0">lock</span>
                    <div>
                        <div class="font-bold text-amber-800 dark:text-amber-300 text-[12px] mb-0.5">Скачивание и каналы связи</div>
                        <div class="text-[11px] text-amber-700 dark:text-amber-400 mb-1.5">Оплатите тариф для PDF, порталов, email и телефонов</div>
                        <div class="flex flex-wrap gap-2">
                            <button onclick="window.complaintChat && window.complaintChat.renderPaywall()" class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-md text-[11px] font-bold transition-colors cursor-pointer">
                                <span class="material-symbols-outlined text-sm">shopping_cart</span> 290 ₽ — Стандартный
                            </button>
                            <a href="/tariffs" class="inline-flex items-center gap-1 px-2 py-1.5 text-amber-600 dark:text-amber-400 text-[11px] hover:underline">
                                Все тарифы →
                            </a>
                        </div>
                    </div>
                </div>
            `;
            container.appendChild(banner);
        }

        // Recipient cards in 2-column grid
        if (results && results.length > 0) {
            const recipientsDiv = document.createElement('div');
            recipientsDiv.className = results.length > 1 ? 'grid grid-cols-2 gap-2' : 'space-y-2';

            results.forEach((result, index) => {
                const card = document.createElement('div');
                card.className = 'gov-card p-2.5 bg-white dark:bg-surface-lighter rounded-lg border border-slate-200 dark:border-white/[0.06]';

                // Header — compact with seal + PDF
                const header = document.createElement('div');
                header.className = 'flex items-center justify-between mb-2 pb-1.5 border-b border-slate-200 dark:border-slate-700';

                const headerText = document.createElement('div');
                headerText.className = 'flex items-center gap-1.5 min-w-0';
                headerText.innerHTML = `
                    <span class="text-[13px] shrink-0">🏛️</span>
                    <span class="font-bold text-[11px] text-slate-800 dark:text-white leading-tight truncate">${this.escapeHtml(result.recipient_name)}</span>
                `;
                header.appendChild(headerText);

                // Download buttons wrapper
                const dlWrap = document.createElement('div');
                dlWrap.className = 'flex gap-1 shrink-0';

                // PDF button
                const pdfBtn = document.createElement('button');
                pdfBtn.className = 'flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] rounded transition-colors';
                if (isPaid) {
                    pdfBtn.className += ' bg-blue-500 hover:bg-blue-600 text-white cursor-pointer';
                    pdfBtn.innerHTML = '<span class="material-symbols-outlined text-[12px]">picture_as_pdf</span> Скачать PDF';
                    pdfBtn.addEventListener('click', () => this.downloadDocument('pdf', result));
                } else {
                    pdfBtn.className += ' bg-slate-300 dark:bg-slate-700 text-slate-500 cursor-not-allowed opacity-60';
                    pdfBtn.innerHTML = '<span class="material-symbols-outlined text-[12px]">lock</span> Скачать PDF';
                }
                dlWrap.appendChild(pdfBtn);

                // DOC button
                const docBtn = document.createElement('button');
                docBtn.className = 'flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] rounded transition-colors';
                if (isPaid) {
                    docBtn.className += ' bg-indigo-500 hover:bg-indigo-600 text-white cursor-pointer';
                    docBtn.innerHTML = '<span class="material-symbols-outlined text-[12px]">description</span> Скачать DOC';
                    docBtn.addEventListener('click', () => this.downloadDocument('doc', result));
                } else {
                    docBtn.className += ' bg-slate-300 dark:bg-slate-700 text-slate-500 cursor-not-allowed opacity-60';
                    docBtn.innerHTML = '<span class="material-symbols-outlined text-[12px]">lock</span> Скачать DOC';
                }
                dlWrap.appendChild(docBtn);
                header.appendChild(dlWrap);
                card.appendChild(header);

                // Contact info — ultra compact
                const contactLines = [];
                if (result.address) contactLines.push(`<div class="flex items-start gap-1"><span class="material-symbols-outlined text-[12px] text-slate-400 shrink-0 mt-px">location_on</span><span class="truncate">${this.escapeHtml(result.address)}</span></div>`);
                if (result.phone) contactLines.push(`<div class="flex items-center gap-1"><span class="material-symbols-outlined text-[12px] text-slate-400">call</span><a href="tel:${result.phone}" class="hover:text-primary">${this.escapeHtml(result.phone)}</a></div>`);
                if (result.working_hours) contactLines.push(`<div class="flex items-center gap-1"><span class="material-symbols-outlined text-[12px] text-slate-400">schedule</span>${this.escapeHtml(result.working_hours)}</div>`);
                if (result.processing_time) contactLines.push(`<div class="flex items-center gap-1"><span class="material-symbols-outlined text-[12px] text-amber-500">timer</span><span class="font-medium">Ответ: ${this.escapeHtml(result.processing_time)}</span></div>`);

                if (contactLines.length > 0) {
                    const contactSection = document.createElement('div');
                    contactSection.className = 'mb-2 text-[10px] text-slate-600 dark:text-slate-300 space-y-0.5';
                    contactSection.innerHTML = contactLines.join('');
                    card.appendChild(contactSection);
                }

                // Action buttons — compact row
                const actionsRow = document.createElement('div');
                actionsRow.className = 'flex gap-1.5';

                // Portal button
                if (result.website) {
                    const portalBtn = document.createElement('a');
                    portalBtn.target = '_blank';
                    portalBtn.rel = 'noopener noreferrer';
                    if (isPaid) {
                        portalBtn.href = result.website;
                        portalBtn.className = 'flex-1 flex items-center justify-center gap-1 px-2 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-md text-[10px] font-semibold transition-colors';
                        portalBtn.innerHTML = `<span class="material-symbols-outlined text-[14px]">language</span> ${result.portal_name ? result.portal_name.substring(0, 15) : 'Портал'}`;
                        portalBtn.addEventListener('click', () => { fetch('/api/track', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event: 'portal_clicked', meta: { recipient: result.recipient_name, url: result.website } }) }); });
                    } else {
                        portalBtn.className = 'flex-1 flex items-center justify-center gap-1 px-2 py-1.5 bg-slate-400 dark:bg-slate-700 text-white rounded-md text-[10px] font-semibold cursor-not-allowed opacity-60';
                        portalBtn.innerHTML = '<span class="material-symbols-outlined text-[14px]">lock</span> Портал';
                    }
                    actionsRow.appendChild(portalBtn);
                }

                // Email button
                if (result.email) {
                    const emailBtn = document.createElement('button');
                    if (isPaid) {
                        emailBtn.className = 'flex-1 flex items-center justify-center gap-1 px-2 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-md text-[10px] font-semibold transition-colors cursor-pointer';
                        emailBtn.innerHTML = '<span class="material-symbols-outlined text-[14px]">mail</span> Email';
                        emailBtn.addEventListener('click', () => { fetch('/api/track', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event: 'email_clicked', meta: { recipient: result.recipient_name, email: result.email } }) }); this.showEmailModal(result); });
                    } else {
                        emailBtn.className = 'flex-1 flex items-center justify-center gap-1 px-2 py-1.5 bg-slate-400 dark:bg-slate-700 text-white rounded-md text-[10px] font-semibold cursor-not-allowed opacity-60';
                        emailBtn.innerHTML = '<span class="material-symbols-outlined text-[14px]">lock</span> Email';
                    }
                    actionsRow.appendChild(emailBtn);
                }

                if (!result.website && !result.email) {
                    const noChannels = document.createElement('div');
                    noChannels.className = 'text-[10px] text-slate-400 italic';
                    noChannels.textContent = 'Каналы связи не найдены';
                    actionsRow.appendChild(noChannels);
                }

                card.appendChild(actionsRow);

                // Auth warning — compact inline
                if (result.auth_required) {
                    const authNote = document.createElement('div');
                    authNote.className = 'mt-1.5 flex items-center gap-1 text-[9px] text-amber-600 dark:text-amber-400';
                    authNote.innerHTML = `<span class="material-symbols-outlined text-[12px]">key</span> ${this.escapeHtml(result.auth_required)}`;
                    card.appendChild(authNote);
                }

                recipientsDiv.appendChild(card);
            });

            container.appendChild(recipientsDiv);
        }

        // New complaint button — compact
        const newBtn = document.createElement('button');
        newBtn.className = 'flex items-center justify-center gap-1.5 w-full p-2 mt-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg transition-colors text-[11px]';
        newBtn.innerHTML = `
            <span class="material-symbols-outlined text-[16px]">add</span>
            <span>Новая жалоба</span>
        `;
        newBtn.addEventListener('click', () => this.restart());
        container.appendChild(newBtn);

        this.optionsContainer.appendChild(container);
    }

    async downloadDocument(format, recipient) {
        try {
            // Get user data from session state
            const stateRes = await fetch(this.getApiEndpoint('/state'));
            const stateData = await stateRes.json();
            const ud = stateData.data?.user_data || {};
            const fio = ud.fio || ud.name || '';
            const address = ud.address || '';
            const phone = ud.phone || '';
            const email = ud.email || '';

            if (!fio || !address) {
                this.showToast('Данные профиля не заполнены. Обновите профиль в Личном кабинете.', 'warning');
                return;
            }

            const applicant = { fio, address, phone, email };

            if (format === 'doc') {
                this.generateDocClientSide(applicant, recipient);
            } else {
                this.generatePdfClientSide(applicant, recipient);
            }
        } catch (e) {
            this.showToast('Ошибка загрузки данных', 'error');
        }
    }

    _buildDocumentHeader(applicant, recipient) {
        const recipientName = recipient.recipient_name || recipient.name || '';
        const recipientAddress = recipient.address || '';

        let header = '<div style="text-align:right;margin-bottom:24px;line-height:1.5;">';
        header += `<p style="margin:0;font-weight:bold;">${this.escapeHtml(recipientName)}</p>`;
        if (recipientAddress) header += `<p style="margin:0;">${this.escapeHtml(recipientAddress)}</p>`;
        header += '<br>';
        header += `<p style="margin:0;">от ${this.escapeHtml(applicant.fio)}</p>`;
        header += `<p style="margin:0;">проживающего по адресу:</p>`;
        header += `<p style="margin:0;">${this.escapeHtml(applicant.address)}</p>`;
        if (applicant.phone) header += `<p style="margin:0;">тел.: ${this.escapeHtml(applicant.phone)}</p>`;
        if (applicant.email) header += `<p style="margin:0;">email: ${this.escapeHtml(applicant.email)}</p>`;
        header += '</div>';
        return header;
    }

    _prepareComplaintText(applicant) {
        let text = this.currentComplaintText || '';
        text = text.replaceAll('[ФИО ЗАЯВИТЕЛЯ]', applicant.fio);
        text = text.replaceAll('[АДРЕС ЗАЯВИТЕЛЯ]', applicant.address);
        text = text.replaceAll('[ТЕЛЕФОН ЗАЯВИТЕЛЯ]', applicant.phone || 'не указан');
        text = text.replaceAll('[EMAIL ЗАЯВИТЕЛЯ]', applicant.email || 'не указан');
        return text;
    }

    _textToHtml(text) {
        return text
            .split('\n')
            .map(line => {
                if (!line.trim()) return '<br>';
                if (line.includes('ЖАЛОБА') || line.includes('ПРОШУ') || line.startsWith('В ')) {
                    return `<p style="font-weight:bold;text-align:center;font-size:15px;margin:12px 0;">${this.escapeHtml(line)}</p>`;
                }
                if (/^\d+\./.test(line.trim())) {
                    return `<p style="margin:4px 0 4px 20px;">${this.escapeHtml(line)}</p>`;
                }
                return `<p style="margin:4px 0;text-indent:20px;">${this.escapeHtml(line)}</p>`;
            })
            .join('\n');
    }

    generatePdfClientSide(applicant, recipient) {
        const recipientName = recipient.recipient_name || recipient.name || '';
        const text = this._prepareComplaintText(applicant);
        const headerHtml = this._buildDocumentHeader(applicant, recipient);
        const bodyHtml = this._textToHtml(text);

        // Open a print-ready window
        const printWindow = window.open('', '_blank');
        if (!printWindow) {
            const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'complaint.txt';
            a.click();
            URL.revokeObjectURL(url);
            return;
        }

        printWindow.document.write(`<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Жалоба — ${this.escapeHtml(recipientName)}</title>
    <style>
        @page { margin: 25mm 20mm; }
        body {
            font-family: 'Times New Roman', 'PT Serif', Georgia, serif;
            font-size: 13px;
            line-height: 1.6;
            color: #000;
            max-width: 700px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        p { margin: 4px 0; }
        @media print {
            body { padding: 0; }
        }
        .print-btn {
            display: block;
            margin: 20px auto;
            padding: 12px 32px;
            background: #2563eb;
            color: #fff;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            cursor: pointer;
            font-weight: bold;
        }
        .print-btn:hover { background: #1d4ed8; }
        @media print { .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="no-print" style="text-align:center;margin-bottom:24px;padding:16px;background:#f0f9ff;border-radius:12px;border:1px solid #bfdbfe;">
        <p style="font-size:14px;color:#1e40af;margin-bottom:12px;">
            <strong>💡 Совет:</strong> Нажмите кнопку ниже и выберите «Сохранить как PDF» в диалоге печати
        </p>
        <button class="print-btn" onclick="window.print()">🖨️ Сохранить как PDF</button>
    </div>
    ${headerHtml}
    <hr style="border:none;border-top:1px solid #ccc;margin:16px 0;">
    ${bodyHtml}
</body>
</html>`);
        printWindow.document.close();
    }

    generateDocClientSide(applicant, recipient) {
        const recipientName = recipient.recipient_name || recipient.name || '';
        const text = this._prepareComplaintText(applicant);
        const headerHtml = this._buildDocumentHeader(applicant, recipient);
        const bodyHtml = this._textToHtml(text);

        const docContent = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="utf-8"><title>Жалоба — ${this.escapeHtml(recipientName)}</title>
<!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View></w:WordDocument></xml><![endif]-->
<style>@page { margin: 25mm 20mm; } body { font-family: 'Times New Roman', serif; font-size: 14px; line-height: 1.6; }</style>
</head><body>${headerHtml}<hr style="border:none;border-top:1px solid #ccc;margin:16px 0;">${bodyHtml}</body></html>`;

        const blob = new Blob(['\ufeff' + docContent], { type: 'application/msword;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const safeName = (recipientName || 'complaint').replace(/[^\w\u0400-\u04ff]/g, '_').substring(0, 30);
        a.href = url;
        a.download = `complaint_${safeName}_${new Date().toISOString().slice(0, 10)}.doc`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        this.showToast('DOC файл скачан', 'success');
    }

    onAutocompleteSelect(item, type) {
        // Store selected data
        if (type === 'company') {
            this.selectedCompanyData = item;
            this.showToast(`✓ ${item.name}`, 'success');

            // Show requisites card in chat
            this.renderCompanyRequisites(item);
        } else if (type === 'address') {
            this.selectedCompanyData = { address: item.value };
            this.showToast(`✓ Адрес выбран`, 'success');
        } else if (type === 'fio') {
            this.selectedCompanyData = { fio: item.value };
            this.showToast(`✓ ${item.value}`, 'success');
        }

        // Mark selection complete
        this.requiresAutocompleteSelection = false;

        // Update indicator
        const indicator = document.getElementById('autocomplete-indicator');
        if (indicator) {
            indicator.innerHTML = `
                <span class="material-symbols-outlined" style="color: #22c55e;">check_circle</span>
                <span style="color: #22c55e;">Выбрано! Нажмите отправить.</span>
            `;
        }

        this.updateSendButton();
    }

    /**
     * Show DaData company requisites as a card in the chat
     */
    renderCompanyRequisites(company) {
        const card = document.createElement('div');
        card.className = 'gov-card p-2.5 bg-white dark:bg-surface-lighter rounded-lg border border-slate-200 dark:border-white/[0.06] mb-2';

        const statusBadge = company.status === 'ACTIVE'
            ? '<span class="text-[9px] px-1.5 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 font-medium">Действующая</span>'
            : company.status === 'LIQUIDATED'
                ? '<span class="text-[9px] px-1.5 py-0.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 font-medium">Ликвидирована</span>'
                : '';

        const typeBadge = company.type === 'INDIVIDUAL'
            ? '<span class="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium">ИП</span>'
            : '<span class="text-[9px] px-1.5 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 font-medium">ЮЛ</span>';

        let rows = '';
        if (company.inn) rows += `<div class="flex items-center gap-1"><span class="text-slate-400 w-12 shrink-0">ИНН</span><span class="font-mono">${this.escapeHtml(company.inn)}</span></div>`;
        if (company.ogrn) rows += `<div class="flex items-center gap-1"><span class="text-slate-400 w-12 shrink-0">ОГРН</span><span class="font-mono">${this.escapeHtml(company.ogrn)}</span></div>`;
        if (company.address) rows += `<div class="flex items-start gap-1"><span class="text-slate-400 w-12 shrink-0">Адрес</span><span>${this.escapeHtml(company.address)}</span></div>`;
        if (company.director) {
            const dirLabel = company.director_post || 'Рук.';
            rows += `<div class="flex items-center gap-1"><span class="text-slate-400 w-12 shrink-0">${this.escapeHtml(dirLabel.substring(0, 12))}</span><span>${this.escapeHtml(company.director)}</span></div>`;
        }

        card.innerHTML = `
            <div class="flex items-center gap-1.5 mb-1.5">
                <span class="text-[13px]">🏢</span>
                <span class="font-bold text-[11px] text-slate-800 dark:text-white leading-tight">${this.escapeHtml(company.name)}</span>
                ${typeBadge} ${statusBadge}
            </div>
            <div class="text-[10px] text-slate-600 dark:text-slate-300 space-y-0.5">
                ${rows}
            </div>
        `;

        // Insert the card into the chat as a system message
        const wrapper = document.createElement('div');
        wrapper.className = 'flex items-start mb-2';
        const bubble = document.createElement('div');
        bubble.className = 'max-w-[85%]';
        bubble.appendChild(card);
        wrapper.appendChild(bubble);
        this.messagesContainer.appendChild(wrapper);
        this.scrollToBottom();
    }

    /**
     * Render Perplexity target suggestions as selectable gov-cards
     */
    renderTargetSuggestions(suggestions) {
        const container = document.createElement('div');
        container.className = 'flex flex-col';

        const header = document.createElement('div');
        header.className = 'flex items-center gap-2 mb-2 pb-1.5 border-b border-slate-200 dark:border-slate-700';
        header.innerHTML = `
            <span class="text-[13px]">🔍</span>
            <span class="text-[11px] font-semibold tracking-wide text-slate-500 dark:text-slate-400">Возможно, вы имели в виду:</span>
        `;
        container.appendChild(header);

        const selectedTargets = new Set();

        const grid = document.createElement('div');
        grid.className = 'grid grid-cols-2 gap-2 mb-2';

        suggestions.forEach((s, i) => {
            const card = document.createElement('label');
            card.className = 'gov-card flex items-start gap-2 p-2 bg-white dark:bg-surface-lighter rounded-lg border border-slate-200 dark:border-white/[0.06] cursor-pointer hover:border-primary/50 transition-all';

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = s.name;
            cb.className = 'mt-0.5 w-3.5 h-3.5 rounded-sm border-slate-300 text-primary focus:ring-primary shrink-0';
            cb.addEventListener('change', () => {
                if (cb.checked) {
                    selectedTargets.add(s.name);
                    card.classList.add('border-primary', 'bg-primary/5');
                } else {
                    selectedTargets.delete(s.name);
                    card.classList.remove('border-primary', 'bg-primary/5');
                }
            });

            const content = document.createElement('div');
            content.className = 'flex-1 min-w-0';

            const typeIcons = { 'organization': '🏢', 'government': '🏛️', 'individual': '👤', 'institution': '🏥' };
            const icon = typeIcons[s.type] || '📋';

            content.innerHTML = `
                <div class="font-semibold text-[11px] text-slate-800 dark:text-white leading-tight mb-0.5">${icon} ${this.escapeHtml(s.name)}</div>
                ${s.description ? `<div class="text-[10px] text-slate-500 dark:text-slate-400 leading-snug line-clamp-2">${this.escapeHtml(s.description)}</div>` : ''}
                ${s.inn ? `<div class="text-[9px] text-slate-400 mt-0.5 font-mono">ИНН: ${this.escapeHtml(s.inn)}</div>` : ''}
            `;

            card.appendChild(cb);
            card.appendChild(content);
            grid.appendChild(card);
        });

        container.appendChild(grid);

        // Action buttons
        const actions = document.createElement('div');
        actions.className = 'flex gap-2';

        const confirmBtn = document.createElement('button');
        confirmBtn.className = 'flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-primary hover:bg-primary-hover text-white rounded-lg text-[11px] font-semibold transition-colors cursor-pointer';
        confirmBtn.innerHTML = '<span class="material-symbols-outlined text-[16px]">check</span> Выбрать отмеченных';
        confirmBtn.addEventListener('click', () => {
            if (selectedTargets.size === 0) {
                this.showToast('Выберите хотя бы одного', 'warning');
                return;
            }
            // Send selected targets as comma-separated to backend
            const targetNames = [...selectedTargets].join(', ');
            this.sendMessage('target_selected:' + targetNames, targetNames);
        });
        actions.appendChild(confirmBtn);

        const skipBtn = document.createElement('button');
        skipBtn.className = 'flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg text-[11px] transition-colors cursor-pointer';
        skipBtn.innerHTML = '<span class="material-symbols-outlined text-[16px]">arrow_forward</span> Никто не подходит';
        skipBtn.addEventListener('click', () => {
            this.sendMessage('target_skip', 'Продолжить без выбора');
        });
        actions.appendChild(skipBtn);

        container.appendChild(actions);

        this.optionsContainer.innerHTML = '';
        this.optionsContainer.appendChild(container);
        this.optionsContainer.classList.remove('hidden');
    }

    renderOptions(options) {
        const grid = document.createElement('div');
        // Center buttons when 3 or fewer, grid otherwise
        if (options.length <= 3) {
            grid.className = 'flex flex-wrap justify-center gap-1.5';
        } else {
            grid.className = 'grid grid-cols-3 gap-1.5';
        }

        const icons = {
            'жкх': { icon: 'home', color: 'emerald' },
            'жилищ': { icon: 'home', color: 'emerald' },
            'работодатель': { icon: 'badge', color: 'amber' },
            'магазин': { icon: 'storefront', color: 'primary' },
            'потребител': { icon: 'shopping_bag', color: 'primary' },
            'госорган': { icon: 'account_balance', color: 'violet' },
            'банк': { icon: 'account_balance_wallet', color: 'cyan' },
            'соседи': { icon: 'groups', color: 'amber' },
            'медицин': { icon: 'local_hospital', color: 'rose' },
            'другое': { icon: 'more_horiz', color: 'slate' },
            'default': { icon: 'arrow_forward', color: 'primary' }
        };

        const colorClasses = {
            'primary': { bg: 'bg-primary/10 dark:bg-primary/20', text: 'text-primary' },
            'emerald': { bg: 'bg-emerald-500/10 dark:bg-emerald-500/20', text: 'text-emerald-600 dark:text-emerald-400' },
            'rose': { bg: 'bg-rose-500/10 dark:bg-rose-500/20', text: 'text-rose-600 dark:text-rose-400' },
            'amber': { bg: 'bg-amber-500/10 dark:bg-amber-500/20', text: 'text-amber-600 dark:text-amber-400' },
            'violet': { bg: 'bg-violet-500/10 dark:bg-violet-500/20', text: 'text-violet-600 dark:text-violet-400' },
            'cyan': { bg: 'bg-cyan-500/10 dark:bg-cyan-500/20', text: 'text-cyan-600 dark:text-cyan-400' },
            'slate': { bg: 'bg-slate-500/10 dark:bg-slate-500/20', text: 'text-slate-600 dark:text-slate-400' },
        };

        // Determine if these are initial categories (have subtitles/descriptions) or quiz options
        const isInitialCategories = options.length <= 6 && this.stepCount <= 1;

        options.forEach(option => {
            const btn = document.createElement('button');
            const textLower = option.text.toLowerCase();
            let matched = icons['default'];
            for (const [key, value] of Object.entries(icons)) {
                if (key !== 'default' && textLower.includes(key)) {
                    matched = value;
                    break;
                }
            }
            const colors = colorClasses[matched.color] || colorClasses['primary'];

            if (isInitialCategories) {
                // Card-style category buttons — strict
                btn.className = 'group flex items-center gap-2 p-2 rounded-md bg-white dark:bg-surface-lighter border border-slate-200 dark:border-white/[0.06] hover:border-primary/50 hover:bg-slate-50 dark:hover:bg-white/[0.03] transition-all duration-150 text-left shadow-soft active:scale-[0.97]';
                btn.innerHTML = `
                    <div class="w-7 h-7 rounded-md ${colors.bg} ${colors.text} flex items-center justify-center shrink-0">
                        <span class="material-icons-round text-[16px]">${matched.icon}</span>
                    </div>
                    <span class="font-medium text-[11.5px] text-slate-700 dark:text-slate-200 leading-tight">${option.text}</span>
                `;
            } else {
                // Quiz option buttons — strict, 2 columns
                btn.className = 'group flex items-center gap-1.5 px-2.5 py-1.5 bg-white dark:bg-surface-lighter hover:bg-slate-50 dark:hover:bg-white/[0.03] border border-slate-200 dark:border-white/[0.06] hover:border-primary/50 rounded-md text-[12px] font-medium transition-all duration-150 active:scale-[0.97] shadow-soft text-left';
                btn.innerHTML = `
                    <span class="w-3.5 h-3.5 rounded-sm border border-slate-300 dark:border-slate-600 group-hover:border-primary group-hover:bg-primary/10 flex items-center justify-center transition-colors shrink-0">
                        <span class="material-icons-round text-[8px] text-primary opacity-0 group-hover:opacity-100">check</span>
                    </span>
                    <span class="text-slate-700 dark:text-slate-300 leading-tight">${option.text}</span>
                `;
                if (options.length > 3) {
                    grid.className = 'grid grid-cols-2 gap-1.5';
                }
            }

            btn.dataset.id = option.id;

            btn.addEventListener('click', () => {
                const messageToSend = option.id || option.text;
                const displayText = option.text;
                this.sendMessage(messageToSend, displayText);
            });

            grid.appendChild(btn);
        });

        this.optionsContainer.appendChild(grid);

        // Hint — encourage precise free-text input (skip for initial categories)
        if (!isInitialCategories) {
            const hint = document.createElement('p');
            hint.className = 'text-[10px] text-slate-400 dark:text-slate-600 text-center mt-1.5 italic';
            hint.textContent = 'Если знаете точнее — напишите своими словами в поле ниже ↓';
            this.optionsContainer.appendChild(hint);
        }
    }

    renderMultiselect(options) {
        const container = document.createElement('div');
        container.className = 'flex flex-col';

        // Header — official style
        const header = document.createElement('div');
        header.className = 'flex items-center gap-2 mb-2 pb-1.5 border-b border-slate-200 dark:border-slate-700';
        header.innerHTML = `
            <span class="text-[13px]">⚖️</span>
            <span class="text-[11px] font-semibold tracking-wide uppercase text-slate-500 dark:text-slate-400" style="font-variant: small-caps; letter-spacing: 0.08em;">Выберите получателей обращения</span>
        `;
        container.appendChild(header);

        // 2-column scrollable grid
        const optionsList = document.createElement('div');
        optionsList.className = 'grid grid-cols-2 gap-2 overflow-y-auto max-h-[50vh] pr-1';

        options.forEach(option => {
            if (option.id === 'custom') return;

            const card = document.createElement('label');
            card.className = 'gov-card flex items-start gap-2 p-2 bg-white dark:bg-surface-lighter rounded-lg border border-slate-200 dark:border-white/[0.06] cursor-pointer hover:border-primary/50 transition-all';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = option.id;
            checkbox.className = 'mt-0.5 w-3.5 h-3.5 rounded-sm border-slate-300 text-primary focus:ring-primary shrink-0';
            checkbox.addEventListener('change', () => {
                if (checkbox.checked) {
                    this.selectedOptions.add(option.id);
                    card.classList.remove('border-slate-200', 'dark:border-white/[0.06]');
                    card.classList.add('border-primary', 'bg-primary/5');
                } else {
                    this.selectedOptions.delete(option.id);
                    card.classList.remove('border-primary', 'bg-primary/5');
                    card.classList.add('border-slate-200', 'dark:border-white/[0.06]');
                }
                this.updateMultiselectSubmit();
            });

            const content = document.createElement('div');
            content.className = 'flex-1 min-w-0';

            // Government seal icon + title
            const titleRow = document.createElement('div');
            titleRow.className = 'flex items-start gap-1 mb-0.5';

            // Determine seal icon by level
            const level = (option.level || '').toLowerCase();
            const sealIcons = { 'федеральный': '🏛️', 'региональный': '🏢', 'местный': '🏠' };
            const sealIcon = sealIcons[level] || '📋';

            const title = document.createElement('div');
            title.className = 'font-semibold text-[11px] text-slate-800 dark:text-white leading-tight';
            title.textContent = `${sealIcon} ${option.text}`;
            titleRow.appendChild(title);
            content.appendChild(titleRow);

            // Badges row — level + effectiveness
            const badgesRow = document.createElement('div');
            badgesRow.className = 'flex flex-wrap gap-1 mb-1';

            if (option.level) {
                const levelBadge = document.createElement('span');
                const levelStyles = {
                    'местный': 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
                    'региональный': 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
                    'федеральный': 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400'
                };
                levelBadge.className = `text-[9px] px-1.5 py-0.5 rounded-full font-medium ${levelStyles[level] || 'bg-slate-100 text-slate-600'}`;
                levelBadge.textContent = option.level;
                badgesRow.appendChild(levelBadge);
            }

            if (option.effectiveness) {
                const effBadge = document.createElement('span');
                const effMap = {
                    'high': { cls: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400', label: '✓ рек.' },
                    'medium': { cls: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400', label: '~ станд.' },
                    'low': { cls: 'bg-slate-100 dark:bg-slate-800 text-slate-500', label: '⚠ кр.мера' }
                };
                const eff = effMap[option.effectiveness] || effMap['medium'];
                effBadge.className = `text-[9px] px-1.5 py-0.5 rounded-full font-medium ${eff.cls}`;
                effBadge.textContent = eff.label;
                badgesRow.appendChild(effBadge);
            }

            if (option.processing_time) {
                const timeBadge = document.createElement('span');
                timeBadge.className = 'text-[9px] px-1.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-medium';
                timeBadge.textContent = `⏱ ${option.processing_time}`;
                badgesRow.appendChild(timeBadge);
            }

            if (badgesRow.children.length > 0) {
                content.appendChild(badgesRow);
            }

            // Reason — truncated to 2 lines
            if (option.reason || option.description) {
                const desc = document.createElement('div');
                desc.className = 'text-[10px] text-slate-500 dark:text-slate-400 leading-snug line-clamp-2';
                desc.textContent = option.reason || option.description;
                content.appendChild(desc);
            }

            // Submission methods — inline compact
            if (option.submission_methods && option.submission_methods.length > 0) {
                const methods = document.createElement('div');
                methods.className = 'flex flex-wrap gap-1 mt-1';
                const icons = { 'Портал': '🌐', 'Email': '📧', 'Личный приём': '👤', 'Почта': '✉️', 'Почта России': '✉️' };
                option.submission_methods.forEach(method => {
                    const badge = document.createElement('span');
                    badge.className = 'text-[8px] px-1 py-0.5 bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 rounded';
                    badge.textContent = `${icons[method] || '📋'} ${method}`;
                    methods.appendChild(badge);
                });
                content.appendChild(methods);
            }

            card.appendChild(checkbox);
            card.appendChild(content);
            optionsList.appendChild(card);
        });

        // Add scrollable grid to container
        container.appendChild(optionsList);

        // Submit button (always visible at bottom)
        const submitBtn = document.createElement('button');
        submitBtn.id = 'multiselect-submit';
        submitBtn.className = 'w-full p-4 bg-primary hover:bg-primary-hover text-white font-semibold rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-4 shrink-0';
        submitBtn.textContent = 'Продолжить';
        submitBtn.disabled = true;
        submitBtn.addEventListener('click', () => {
            if (this.selectedOptions.size > 0) {
                const selectedIds = Array.from(this.selectedOptions).join(',');
                const selectedNames = options
                    .filter(o => this.selectedOptions.has(o.id))
                    .map(o => o.text)
                    .join(', ');
                this.sendMessage(selectedIds, selectedNames);
            }
        });
        container.appendChild(submitBtn);

        this.optionsContainer.appendChild(container);
    }

    updateMultiselectSubmit() {
        const btn = document.getElementById('multiselect-submit');
        if (btn) {
            btn.disabled = this.selectedOptions.size === 0;
            btn.textContent = this.selectedOptions.size > 0
                ? `Продолжить (${this.selectedOptions.size})`
                : 'Продолжить';
        }
    }



    showTyping(show) {
        if (show) {
            this.typingIndicator.classList.remove('hidden');
            this.scrollToBottom();
        } else {
            this.typingIndicator.classList.add('hidden');
        }
    }

    updateProgress() {
        if (this.stepCount > 0) {
            this.progressContainer.classList.remove('hidden');
            const progress = Math.min((this.stepCount / 10) * 100, 100);
            this.progressBar.style.width = `${progress}%`;
            this.progressStep.textContent = `Шаг ${this.stepCount}`;

            const labels = ['Категория', 'Детали', 'Доказательства', 'Ущерб', 'Контакты', 'Получатели', 'Предпросмотр'];
            this.progressLabel.textContent = labels[Math.min(this.stepCount - 1, labels.length - 1)] || 'Заполнение';
        } else {
            this.progressContainer.classList.add('hidden');
        }
    }

    updateBackButton(show) {
        if (show) {
            this.backBtn.classList.remove('hidden');
        } else {
            this.backBtn.classList.add('hidden');
        }
    }

    updateCharCount() {
        const count = this.messageInput.value.length;
        if (count > 100) {
            this.charCount.classList.remove('hidden');
            this.charCount.textContent = `${count} / 2000`;
        } else {
            this.charCount.classList.add('hidden');
        }
    }

    updateSendButton() {
        const hasText = this.messageInput.value.trim().length > 0;

        // Block if autocomplete selection is required but not made
        // (company autocomplete never blocks — free text allowed)
        if (this.requiresAutocompleteSelection && this.autocompleteType !== 'company' && hasText) {
            this.sendBtn.disabled = true;
            this.sendBtn.title = 'Сначала выберите из списка подсказок';
        } else {
            this.sendBtn.disabled = !hasText;
            this.sendBtn.title = '';
        }
    }

    autoResizeTextarea() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 150) + 'px';
    }

    scrollToBottom() {
        setTimeout(() => {
            const chatContainer = document.getElementById('chat-container');
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }, 100);
    }

    async showEmailModal(result) {
        // Extract email data from result
        const email = result.email || '';
        const recipientName = result.recipient_name || 'Получатель';

        // Get user data for cover letter
        let fio = '';
        let categoryName = '';
        try {
            const stateRes = await fetch(this.getApiEndpoint('/state'));
            const stateData = await stateRes.json();
            const ud = stateData.data?.user_data || {};
            fio = ud.fio || ud.name || '';
            categoryName = stateData.data?.category_name || '';
        } catch (e) { /* ignore */ }

        // Build cover letter
        const today = new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
        const subject = categoryName
            ? `Обращение (жалоба) — ${categoryName}`
            : 'Обращение (жалоба)';

        const coverLetter = [
            `Уважаемые сотрудники ${recipientName}!`,
            '',
            `Направляю Вам обращение (жалобу)${categoryName ? ' по вопросу: ' + categoryName : ''}.`,
            '',
            'Полный текст обращения изложен в прикреплённом PDF-файле.',
            '',
            '⚠️ ВАЖНО: Пожалуйста, прикрепите к этому письму PDF-файл жалобы, скачанный ранее.',
            '',
            'Прошу рассмотреть обращение в установленные законом сроки и направить ответ по указанному адресу.',
            '',
            'С уважением,',
            fio || '[ФИО]',
            today,
        ].join('\n');

        // Encode for URLs
        const encodedSubject = encodeURIComponent(subject);
        const encodedBody = encodeURIComponent(coverLetter);
        const encodedEmail = encodeURIComponent(email);

        // mailto link with cover letter
        const mailtoLink = `mailto:${email}?subject=${encodedSubject}&body=${encodedBody}`;

        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4';
        overlay.id = 'email-modal';

        // Modal content
        overlay.innerHTML = `
            <div class="bg-white dark:bg-surface-dark rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-hidden animate-in fade-in zoom-in duration-200">
                <!-- Header -->
                <div class="p-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                    <h3 class="text-lg font-bold text-slate-900 dark:text-white">📧 Отправить в ${this.escapeHtml(recipientName)}</h3>
                    <button id="close-email-modal" class="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
                        <span class="material-symbols-outlined">close</span>
                    </button>
                </div>
                
                <!-- Content -->
                <div class="p-4 space-y-4 overflow-y-auto max-h-[60vh]">
                    <!-- Email address -->
                    <div class="space-y-1">
                        <label class="text-sm font-medium text-slate-500 dark:text-slate-400">Адрес получателя</label>
                        <div class="flex items-center gap-2">
                            <input type="text" readonly value="${this.escapeHtml(email)}" 
                                class="flex-1 p-3 bg-slate-100 dark:bg-surface-lighter rounded-lg text-slate-900 dark:text-white font-mono text-sm">
                            <button id="copy-email" class="p-3 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 rounded-lg transition-colors" title="Копировать">
                                <span class="material-symbols-outlined text-slate-700 dark:text-slate-300">content_copy</span>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Subject -->
                    <div class="space-y-1">
                        <label class="text-sm font-medium text-slate-500 dark:text-slate-400">Тема письма</label>
                        <div class="flex items-center gap-2">
                            <input type="text" readonly value="${this.escapeHtml(subject)}" 
                                class="flex-1 p-3 bg-slate-100 dark:bg-surface-lighter rounded-lg text-slate-900 dark:text-white text-sm">
                            <button id="copy-subject" class="p-3 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 rounded-lg transition-colors" title="Копировать">
                                <span class="material-symbols-outlined text-slate-700 dark:text-slate-300">content_copy</span>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Cover letter preview -->
                    <div class="space-y-1">
                        <label class="text-sm font-medium text-slate-500 dark:text-slate-400">Сопроводительное письмо</label>
                        <div class="relative">
                            <textarea readonly 
                                class="w-full p-3 bg-slate-100 dark:bg-surface-lighter rounded-lg text-slate-900 dark:text-white text-sm h-36 resize-none">${this.escapeHtml(coverLetter)}</textarea>
                            <button id="copy-body" class="absolute top-2 right-2 p-2 bg-white dark:bg-slate-600 hover:bg-slate-50 dark:hover:bg-slate-500 rounded-lg shadow-sm transition-colors" title="Копировать всё">
                                <span class="material-symbols-outlined text-slate-700 dark:text-slate-300 text-sm">content_copy</span>
                            </button>
                        </div>
                    </div>
                    
                    <!-- PDF reminder -->
                    <div class="flex items-center gap-3 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                        <span class="text-amber-600 dark:text-amber-400">📎</span>
                        <span class="text-sm text-amber-800 dark:text-amber-300">Сначала скачайте PDF-файл жалобы, затем прикрепите его к письму!</span>
                    </div>
                </div>
                
                <!-- Webmail buttons -->
                <div class="p-4 border-t border-slate-200 dark:border-slate-700 space-y-3">
                    <p class="text-sm text-slate-500 dark:text-slate-400 text-center">Выберите вашу почту:</p>
                    <div class="grid grid-cols-3 gap-2">
                        <a href="https://mail.google.com/mail/?view=cm&to=${encodedEmail}&su=${encodedSubject}&body=${encodedBody}" 
                           target="_blank" rel="noopener"
                           class="flex flex-col items-center gap-1 p-3 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/40 rounded-xl transition-colors">
                            <span class="text-2xl">📧</span>
                            <span class="text-xs font-medium text-red-700 dark:text-red-400">Gmail</span>
                        </a>
                        <a href="https://mail.yandex.ru/compose?to=${encodedEmail}&subject=${encodedSubject}&body=${encodedBody}" 
                           target="_blank" rel="noopener"
                           class="flex flex-col items-center gap-1 p-3 bg-yellow-50 dark:bg-yellow-900/20 hover:bg-yellow-100 dark:hover:bg-yellow-900/40 rounded-xl transition-colors">
                            <span class="text-2xl">📮</span>
                            <span class="text-xs font-medium text-yellow-700 dark:text-yellow-400">Яндекс</span>
                        </a>
                        <a href="https://e.mail.ru/compose/?to=${encodedEmail}&subject=${encodedSubject}&body=${encodedBody}" 
                           target="_blank" rel="noopener"
                           class="flex flex-col items-center gap-1 p-3 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/40 rounded-xl transition-colors">
                            <span class="text-2xl">💌</span>
                            <span class="text-xs font-medium text-blue-700 dark:text-blue-400">Mail.ru</span>
                        </a>
                    </div>
                    
                    <!-- Fallback mailto -->
                    <a href="${mailtoLink}" 
                       class="flex items-center justify-center gap-2 w-full p-3 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-xl transition-colors">
                        <span class="material-symbols-outlined">open_in_new</span>
                        <span>Открыть в почтовом клиенте</span>
                    </a>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        // Event handlers
        document.getElementById('close-email-modal').addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });

        document.getElementById('copy-email').addEventListener('click', () => {
            navigator.clipboard.writeText(email);
            this.showToast('📋 Email скопирован', 'success');
        });

        document.getElementById('copy-subject').addEventListener('click', () => {
            navigator.clipboard.writeText(subject);
            this.showToast('📋 Тема скопирована', 'success');
        });

        document.getElementById('copy-body').addEventListener('click', () => {
            navigator.clipboard.writeText(coverLetter);
            this.showToast('📋 Текст скопирован', 'success');
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }


    async goBack() {
        if (this.isLoading) return;

        try {
            const endpoint = this.getApiEndpoint('/back');
            const response = await fetch(endpoint, { method: 'POST' });
            const data = await response.json();

            if (data.success) {
                this.stepCount = Math.max(0, this.stepCount - 1);
                await this.loadState();
                this.showToast('Вернулись на шаг назад', 'success');
            } else {
                this.showToast(data.error || 'Невозможно вернуться назад', 'warning');
            }
        } catch (error) {
            this.showToast('Ошибка. Попробуйте ещё раз.', 'error');
        }
    }

    async restart() {
        if (this.isLoading) return;

        if (!confirm('Начать заново? Текущий прогресс будет потерян.')) {
            return;
        }

        try {
            const endpoint = this.getApiEndpoint('/restart');
            const response = await fetch(endpoint, { method: 'POST' });
            const data = await response.json();

            if (data.success) {
                this.stepCount = 0;
                await this.loadState();
                this.showToast('Диалог начат заново', 'success');
            }
        } catch (error) {
            this.showToast('Ошибка. Обновите страницу.', 'error');
        }
    }

    // ==================== COMPLAINT HISTORY ====================

    async openHistory() {
        try {
            const res = await fetch(this.getApiEndpoint('/complaints/history'));
            const data = await res.json();
            const complaints = data.complaints || [];

            // Remove existing modal if any
            const existing = document.getElementById('history-modal');
            if (existing) existing.remove();

            const modal = document.createElement('div');
            modal.id = 'history-modal';
            modal.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;';
            modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

            let html = `<div style="background:#0f1117;border:1px solid #2a3347;border-radius:12px;width:100%;max-width:700px;max-height:85vh;overflow-y:auto;margin:16px;padding:24px;box-shadow:0 20px 40px rgba(0,0,0,0.5);">`;
            html += `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
                <h2 style="font-size:18px;font-weight:600;color:#fff;display:flex;align-items:center;gap:8px;">
                    <span class="material-icons-round" style="color:#3d5a80;">history</span> История жалоб
                </h2>
                <button onclick="document.getElementById('history-modal').remove()" style="color:#8896b3;background:none;border:none;cursor:pointer;font-size:24px;">&times;</button>
            </div>`;

            if (complaints.length === 0) {
                html += `<p style="color:#8896b3;text-align:center;padding:40px 0;">У вас пока нет сохранённых жалоб</p>`;
            } else {
                complaints.forEach((c, i) => {
                    const date = c.created_at ? new Date(c.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
                    const recipientNames = (c.recipients || []).map(r => r.recipient_name || r.name || '?').join(', ');
                    const textPreview = (c.complaint_text || '').substring(0, 150) + ((c.complaint_text || '').length > 150 ? '...' : '');

                    html += `<div style="background:#181b25;border:1px solid #2a3347;border-radius:8px;padding:16px;margin-bottom:12px;cursor:pointer;transition:border-color 0.2s;" 
                        onmouseover="this.style.borderColor='#3d5a80'" onmouseout="this.style.borderColor='#2a3347'"
                        onclick="window.chatApp.openComplaintDetail('${c.id}')">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                            <span style="background:rgba(59,130,246,0.15);color:#3b82f6;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:500;">${c.category_name || 'Жалоба'}</span>
                            <span style="font-size:11px;color:#8896b3;">${date}</span>
                        </div>
                        <p style="font-size:12px;color:#cbd5e1;line-height:1.5;margin-bottom:6px;">${this.escapeHtml(textPreview)}</p>
                        <div style="font-size:11px;color:#8896b3;">→ ${recipientNames || 'Нет получателей'} · ${(c.recipients || []).length} адресатов</div>
                    </div>`;
                });
            }

            html += `</div>`;
            modal.innerHTML = html;
            document.body.appendChild(modal);
            // Close on Escape
            const escHandler = (e) => { if (e.key === 'Escape') { modal.remove(); document.removeEventListener('keydown', escHandler); } };
            document.addEventListener('keydown', escHandler);
        } catch (e) {
            this.showToast('Ошибка загрузки истории', 'error');
        }
    }

    async openComplaintDetail(id) {
        try {
            const res = await fetch(this.getApiEndpoint(`/complaints/${id}`));
            const data = await res.json();
            if (data.error) { this.showToast(data.error, 'error'); return; }
            const c = data.complaint;

            const modal = document.getElementById('history-modal');
            if (!modal) return;

            const date = c.created_at ? new Date(c.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';

            let html = `<div style="background:#0f1117;border:1px solid #2a3347;border-radius:12px;width:100%;max-width:700px;max-height:85vh;overflow-y:auto;margin:16px;padding:24px;box-shadow:0 20px 40px rgba(0,0,0,0.5);">`;

            // Header
            html += `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <button onclick="window.chatApp.openHistory()" style="color:#8896b3;background:none;border:none;cursor:pointer;display:flex;align-items:center;">
                        <span class="material-icons-round" style="font-size:20px;">arrow_back</span>
                    </button>
                    <span style="background:rgba(59,130,246,0.15);color:#3b82f6;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:500;">${c.category_name || 'Жалоба'}</span>
                    <span style="font-size:11px;color:#8896b3;">${date}</span>
                </div>
                <button onclick="document.getElementById('history-modal').remove()" style="color:#8896b3;background:none;border:none;cursor:pointer;font-size:24px;">&times;</button>
            </div>`;

            // Complaint text
            html += `<div style="background:#181b25;border:1px solid #2a3347;border-radius:8px;padding:16px;margin-bottom:16px;">
                <div style="font-size:11px;color:#8896b3;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">Текст жалобы</div>
                <div style="font-size:13px;color:#e2e8f0;line-height:1.7;white-space:pre-line;max-height:300px;overflow-y:auto;">${this.escapeHtml(c.complaint_text || '')}</div>
            </div>`;

            // Recipients
            const recipients = c.recipients || [];
            html += `<div style="font-size:11px;color:#8896b3;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">Адресаты (${recipients.length})</div>`;

            recipients.forEach(r => {
                html += `<div style="background:#181b25;border:1px solid #2a3347;border-radius:8px;padding:14px;margin-bottom:8px;">
                    <div style="font-size:14px;font-weight:600;color:#fff;margin-bottom:6px;">${this.escapeHtml(r.recipient_name || r.name || '?')}</div>`;

                const details = [];
                if (r.email) details.push(`<div style="display:flex;align-items:center;gap:6px;"><span class="material-symbols-outlined" style="font-size:14px;color:#22c55e;">mail</span> <a href="mailto:${r.email}" style="color:#93c5fd;font-size:12px;">${r.email}</a></div>`);
                if (r.website) details.push(`<div style="display:flex;align-items:center;gap:6px;"><span class="material-symbols-outlined" style="font-size:14px;color:#a78bfa;">language</span> <a href="${r.website}" target="_blank" style="color:#93c5fd;font-size:12px;">${r.portal_name || r.website}</a></div>`);
                if (r.address) details.push(`<div style="display:flex;align-items:center;gap:6px;"><span class="material-symbols-outlined" style="font-size:14px;color:#f59e0b;">location_on</span> <span style="color:#cbd5e1;font-size:12px;">${this.escapeHtml(r.address)}</span></div>`);
                if (r.phone) details.push(`<div style="display:flex;align-items:center;gap:6px;"><span class="material-symbols-outlined" style="font-size:14px;color:#3b82f6;">call</span> <span style="color:#cbd5e1;font-size:12px;">${r.phone}</span></div>`);
                if (r.working_hours) details.push(`<div style="display:flex;align-items:center;gap:6px;"><span class="material-symbols-outlined" style="font-size:14px;color:#8b5cf6;">schedule</span> <span style="color:#cbd5e1;font-size:12px;">${this.escapeHtml(r.working_hours)}</span></div>`);
                if (r.processing_time) details.push(`<div style="display:flex;align-items:center;gap:6px;"><span class="material-symbols-outlined" style="font-size:14px;color:#ef4444;">timer</span> <span style="color:#cbd5e1;font-size:12px;">${this.escapeHtml(r.processing_time)}</span></div>`);

                html += `<div style="display:flex;flex-direction:column;gap:4px;">${details.join('')}</div>`;

                if (r.tips) html += `<div style="margin-top:8px;padding:8px 10px;background:rgba(59,130,246,0.08);border-radius:6px;font-size:11px;color:#93c5fd;">💡 ${this.escapeHtml(r.tips)}</div>`;
                html += `</div>`;
            });

            // Restore button 
            html += `<button onclick="window.chatApp.restoreComplaint('${c.id}')" 
                style="width:100%;margin-top:12px;padding:10px;background:#3d5a80;color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;transition:background 0.2s;"
                onmouseover="this.style.background='#2c4a6e'" onmouseout="this.style.background='#3d5a80'">
                <span class="material-icons-round" style="font-size:18px;">replay</span> Загрузить в чат
            </button>`;

            html += `</div>`;
            modal.innerHTML = html;
        } catch (e) {
            this.showToast('Ошибка загрузки жалобы', 'error');
        }
    }

    async restoreComplaint(id) {
        try {
            const res = await fetch(this.getApiEndpoint(`/complaints/${id}`));
            const data = await res.json();
            if (data.error) { this.showToast(data.error, 'error'); return; }
            const c = data.complaint;

            // Close modal
            const modal = document.getElementById('history-modal');
            if (modal) modal.remove();

            // Render the complaint text as assistant message
            this.messagesContainer.innerHTML = '';
            this.renderMessage('assistant', `📋 **Жалоба из истории** (${c.category_name || ''})\n\n${c.complaint_text || ''}`);

            // Show sending results cards
            if (c.recipients && c.recipients.length > 0) {
                this.renderSendingResults(c.recipients, this.isPaid);
            }

            this.scrollToBottom();
            this.showToast('Жалоба загружена из истории', 'success');
        } catch (e) {
            this.showToast('Ошибка восстановления', 'error');
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showToast(message, type = 'info') {
        const colors = {
            'success': 'bg-green-500',
            'error': 'bg-red-500',
            'warning': 'bg-yellow-500',
            'info': 'bg-blue-500'
        };

        const toast = document.createElement('div');
        toast.className = `${colors[type] || colors.info} text-white px-4 py-3 rounded-lg shadow-lg animate-fade-in flex items-center gap-2`;

        const icons = {
            'success': 'check_circle',
            'error': 'error',
            'warning': 'warning',
            'info': 'info'
        };

        toast.innerHTML = `
            <span class="material-symbols-outlined text-[20px]">${icons[type] || icons.info}</span>
            <span class="text-sm font-medium">${message}</span>
        `;

        this.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ==================== PAYMENT SYSTEM ====================

    applyCopyProtection() {
        // Already active?
        if (this._copyProtectionActive) return;
        this._copyProtectionActive = true;

        // 1) CSS user-select: none on the entire chat container
        this.messagesContainer.style.userSelect = 'none';
        this.messagesContainer.style.webkitUserSelect = 'none';
        this.messagesContainer.classList.add('paywall-protected');

        // 2) Block copy / cut / selectstart / contextmenu / dragstart events
        this._protectionHandlers = {
            copy: (e) => {
                if (!this._copyProtectionActive) return;
                e.preventDefault();
                e.stopPropagation();
                this.showToast('Оплатите тариф для копирования текста', 'warning');
            },
            cut: (e) => {
                if (!this._copyProtectionActive) return;
                e.preventDefault();
            },
            selectstart: (e) => {
                if (!this._copyProtectionActive) return;
                // Allow selection in input/textarea only
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                e.preventDefault();
            },
            contextmenu: (e) => {
                if (!this._copyProtectionActive) return;
                // Block only inside chat
                if (this.messagesContainer.contains(e.target)) {
                    e.preventDefault();
                    this.showToast('Оплатите тариф для копирования текста', 'warning');
                }
            },
            dragstart: (e) => {
                if (!this._copyProtectionActive) return;
                if (this.messagesContainer.contains(e.target)) {
                    e.preventDefault();
                }
            },
            keydown: (e) => {
                if (!this._copyProtectionActive) return;
                // Block Ctrl+C, Ctrl+A, Ctrl+X inside chat area
                if ((e.ctrlKey || e.metaKey) && ['c', 'a', 'x'].includes(e.key.toLowerCase())) {
                    // Allow in inputs/textareas
                    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                    e.preventDefault();
                    if (e.key.toLowerCase() === 'c') {
                        this.showToast('Оплатите тариф для копирования текста', 'warning');
                    }
                }
            }
        };

        // Attach all handlers to document (capture phase to intercept early)
        Object.entries(this._protectionHandlers).forEach(([event, handler]) => {
            document.addEventListener(event, handler, true);
        });

        // 3) Clear any existing selection
        window.getSelection()?.removeAllRanges();
    }

    removeCopyProtection() {
        this._copyProtectionActive = false;

        // Remove CSS
        this.messagesContainer.style.userSelect = '';
        this.messagesContainer.style.webkitUserSelect = '';
        this.messagesContainer.classList.remove('paywall-protected');

        // Detach all event handlers
        if (this._protectionHandlers) {
            Object.entries(this._protectionHandlers).forEach(([event, handler]) => {
                document.removeEventListener(event, handler, true);
            });
            this._protectionHandlers = null;
        }

        // Clean up legacy overlays/blur if present
        document.querySelectorAll('.paywall-overlay').forEach(el => el.remove());
        document.querySelectorAll('.paywall-blur').forEach(el => {
            el.style.cssText = '';
            el.classList.remove('paywall-blur');
        });
    }

    updateUserHeader(userName) {
        const area = document.getElementById('user-header-area');
        if (!area) return;
        // Only update if not already showing a user name
        if (area.querySelector('.user-name-display')) return;
        area.innerHTML = `
            <a href="/account"
                class="flex items-center gap-1.5 px-2 py-1.5 rounded-md text-[11px] text-slate-400 dark:text-slate-300 hover:text-primary hover:bg-slate-100 dark:hover:bg-white/5 transition-colors animate-fade-in"
                title="\u041b\u0438\u0447\u043d\u044b\u0439 \u043a\u0430\u0431\u0438\u043d\u0435\u0442">
                <span class="material-icons-round text-[16px]">person</span>
                <span class="truncate max-w-[100px] user-name-display">${this.escapeHtml(userName)}</span>
            </a>
        `;
    }

    async renderPaywall() {
        this.optionsContainer.innerHTML = '';

        const wrapper = document.createElement('div');
        wrapper.className = 'space-y-3 animate-fade-in';

        // Header
        const header = document.createElement('div');
        header.className = 'text-center py-2';
        header.innerHTML = `
            <div class="flex items-center justify-center gap-2 mb-1">
                <span class="material-icons-round text-primary text-xl">lock</span>
                <span class="font-semibold text-[15px] text-slate-800 dark:text-white">\u0416\u0430\u043b\u043e\u0431\u0430 \u0433\u043e\u0442\u043e\u0432\u0430</span>
            </div>
            <p class="text-[12px] text-slate-500 dark:text-slate-400">\u041e\u043f\u043b\u0430\u0442\u0438\u0442\u0435 \u0434\u043e\u0441\u0442\u0443\u043f, \u0447\u0442\u043e\u0431\u044b \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0442\u0435\u043a\u0441\u0442, \u0441\u043a\u0430\u0447\u0430\u0442\u044c PDF \u0438 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c</p>
        `;
        wrapper.appendChild(header);

        // Fetch tariffs
        try {
            const response = await fetch(this.getApiEndpoint('/tariffs'));
            const data = await response.json();

            if (data.paid) {
                this.isPaid = true;
                this.removeBlurProtection();
                this.loadState();
                return;
            }

            const grid = document.createElement('div');
            grid.className = 'grid grid-cols-1 sm:grid-cols-2 gap-2';

            data.tariffs.forEach(tariff => {
                const card = document.createElement('button');
                const isPopular = tariff.popular;
                card.className = `relative p-3 rounded-lg border text-left transition-all duration-150 active:scale-[0.97] ${isPopular
                    ? 'border-primary bg-primary/5 dark:bg-primary/10 shadow-glow'
                    : 'border-slate-200 dark:border-white/[0.06] bg-white dark:bg-surface-lighter hover:border-primary/40'
                    }`;

                const periodLabel = tariff.period ? `/${tariff.period}` : '';
                card.innerHTML = `
                    ${isPopular ? '<div class="absolute -top-2 left-1/2 -translate-x-1/2 bg-primary text-white text-[9px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">\u041f\u043e\u043f\u0443\u043b\u044f\u0440\u043d\u044b\u0439</div>' : ''}
                    <div class="font-semibold text-[13px] text-slate-800 dark:text-white mb-1">${tariff.name}</div>
                    <div class="flex items-baseline gap-0.5 mb-2">
                        <span class="text-[22px] font-bold text-primary">${tariff.price}</span>
                        <span class="text-[11px] text-slate-400">\u20bd${periodLabel}</span>
                    </div>
                    <ul class="space-y-1">
                        ${tariff.features.map(f => `
                            <li class="flex items-center gap-1.5 text-[11px] text-slate-600 dark:text-slate-300">
                                <span class="material-icons-round text-primary text-[12px]">check</span>
                                ${f}
                            </li>
                        `).join('')}
                    </ul>
                `;

                card.addEventListener('click', () => this.processPayment(tariff.id));
                grid.appendChild(card);
            });

            wrapper.appendChild(grid);

            // Security note
            const note = document.createElement('div');
            note.className = 'flex items-center justify-center gap-1.5 text-[10px] text-slate-400 dark:text-slate-500 pt-1';
            note.innerHTML = `
                <span class="material-icons-round text-[14px]">verified_user</span>
                <span>\u0411\u0435\u0437\u043e\u043f\u0430\u0441\u043d\u0430\u044f \u043e\u043f\u043b\u0430\u0442\u0430 \u0447\u0435\u0440\u0435\u0437 \u042e\u041a\u0430\u0441\u0441\u0443</span>
            `;
            wrapper.appendChild(note);

        } catch (error) {
            wrapper.innerHTML = `
                <div class="text-center py-4 text-slate-500 dark:text-slate-400">
                    <span class="material-icons-round text-3xl mb-2">error_outline</span>
                    <p class="text-sm">\u041e\u0448\u0438\u0431\u043a\u0430 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438 \u0442\u0430\u0440\u0438\u0444\u043e\u0432. \u041e\u0431\u043d\u043e\u0432\u0438\u0442\u0435 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443.</p>
                </div>
            `;
        }

        this.optionsContainer.appendChild(wrapper);
    }

    async processPayment(tariffId) {
        try {
            this.showToast('\u0421\u043e\u0437\u0434\u0430\u0451\u043c \u043f\u043b\u0430\u0442\u0451\u0436...', 'info');

            const response = await fetch(this.getApiEndpoint('/pay'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tariff_id: tariffId }),
            });

            const data = await response.json();

            if (data.error) {
                this.showToast(data.error, 'error');
                return;
            }

            if (data.confirmation_url) {
                // Start polling for payment status before redirect
                this.startPaymentPolling();
                // Redirect to YooKassa
                window.open(data.confirmation_url, '_blank');
                this.showToast('\u041e\u043f\u043b\u0430\u0442\u0438\u0442\u0435 \u0432 \u043e\u0442\u043a\u0440\u044b\u0432\u0448\u0435\u043c\u0441\u044f \u043e\u043a\u043d\u0435, \u0437\u0430\u0442\u0435\u043c \u0432\u0435\u0440\u043d\u0438\u0442\u0435\u0441\u044c \u0441\u044e\u0434\u0430', 'info');
            }
        } catch (error) {
            this.showToast('\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u043e\u0437\u0434\u0430\u043d\u0438\u044f \u043f\u043b\u0430\u0442\u0435\u0436\u0430', 'error');
        }
    }

    startPaymentPolling() {
        // Poll every 3 seconds for up to 5 minutes
        let attempts = 0;
        const maxAttempts = 100;

        if (this.paymentPollingInterval) {
            clearInterval(this.paymentPollingInterval);
        }

        this.paymentPollingInterval = setInterval(async () => {
            attempts++;
            if (attempts > maxAttempts) {
                clearInterval(this.paymentPollingInterval);
                this.paymentPollingInterval = null;
                return;
            }

            try {
                const response = await fetch(this.getApiEndpoint('/payment/status'));
                const data = await response.json();

                if (data.paid) {
                    clearInterval(this.paymentPollingInterval);
                    this.paymentPollingInterval = null;
                    this.isPaid = true;
                    this.tariffLevel = data.tariff_level || 'standard';
                    this.removeCopyProtection();
                    this.showToast(`\u041e\u043f\u043b\u0430\u0442\u0430 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0430! \u0422\u0430\u0440\u0438\u0444: ${data.tariff}`, 'success');
                    // Reload state to show full content
                    await this.loadState();
                } else if (data.status === 'canceled') {
                    clearInterval(this.paymentPollingInterval);
                    this.paymentPollingInterval = null;
                    this.showToast('\u041f\u043b\u0430\u0442\u0451\u0436 \u043e\u0442\u043c\u0435\u043d\u0451\u043d', 'warning');
                }
            } catch (e) {
                // Silently continue polling
            }
        }, 3000);
    }
}


/**
 * Autocomplete Component
 * Provides suggestions for companies, addresses, and FIO
 */
class Autocomplete {
    constructor(inputElement, type, onSelect) {
        this.input = inputElement;
        this.type = type; // 'company', 'address', 'fio'
        this.onSelect = onSelect;
        this.dropdown = null;
        this.debounceTimer = null;
        this.selectedIndex = -1;
        this.suggestions = [];

        this.init();
    }

    init() {
        // Create dropdown container
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'autocomplete-dropdown hidden';
        this.input.parentNode.style.position = 'relative';
        this.input.parentNode.appendChild(this.dropdown);

        // Track if we're interacting with dropdown
        this.isMouseOverDropdown = false;

        // Bind events
        this.inputHandler = () => this.onInput();
        this.keydownHandler = (e) => this.onKeydown(e);
        this.blurHandler = () => {
            // Only hide if not hovering over dropdown
            setTimeout(() => {
                if (!this.isMouseOverDropdown) {
                    this.hide();
                }
            }, 150);
        };
        this.focusHandler = () => {
            if (this.input.value.length >= 2) {
                this.search(this.input.value);
            }
        };

        this.input.addEventListener('input', this.inputHandler);
        this.input.addEventListener('keydown', this.keydownHandler);
        this.input.addEventListener('blur', this.blurHandler);
        this.input.addEventListener('focus', this.focusHandler);

        // Track mouse over dropdown
        this.dropdown.addEventListener('mouseenter', () => {
            this.isMouseOverDropdown = true;
        });
        this.dropdown.addEventListener('mouseleave', () => {
            this.isMouseOverDropdown = false;
        });

        // Prevent blur when clicking dropdown
        this.dropdown.addEventListener('mousedown', (e) => {
            e.preventDefault();
        });
    }

    onInput() {
        const query = this.input.value.trim();

        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        if (query.length < 2) {
            this.hide();
            return;
        }

        this.debounceTimer = setTimeout(() => {
            this.search(query);
        }, 300);
    }

    async search(query) {
        const endpoint = `/api/suggest/${this.type}?q=${encodeURIComponent(query)}`;

        try {
            const response = await fetch(endpoint);
            const data = await response.json();

            this.suggestions = data.suggestions || [];
            this.render();
        } catch (error) {
            console.error('Autocomplete error:', error);
            this.hide();
        }
    }

    render() {
        if (this.suggestions.length === 0) {
            this.hide();
            return;
        }

        this.dropdown.innerHTML = '';
        this.selectedIndex = -1;

        this.suggestions.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'autocomplete-item';

            if (this.type === 'company') {
                div.innerHTML = `
                    <div class="ac-company-name">${this.escapeHtml(item.name)}</div>
                    <div class="ac-company-details">
                        <span class="ac-inn">ИНН: ${item.inn || 'н/д'}</span>
                        ${item.address ? `<span class="text-text-muted text-xs">${this.escapeHtml(item.address.substring(0, 50))}...</span>` : ''}
                    </div>
                `;
            } else if (this.type === 'address') {
                div.innerHTML = `<div class="text-white">${this.escapeHtml(item.value)}</div>`;
            } else if (this.type === 'fio') {
                div.innerHTML = `<div class="text-white">${this.escapeHtml(item.value)}</div>`;
            }

            div.addEventListener('click', () => this.select(index));
            div.addEventListener('mouseenter', () => {
                this.selectedIndex = index;
                this.updateSelection();
            });

            this.dropdown.appendChild(div);
        });

        this.dropdown.classList.remove('hidden');
    }

    onKeydown(e) {
        if (this.dropdown.classList.contains('hidden')) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.selectedIndex = Math.min(this.selectedIndex + 1, this.suggestions.length - 1);
            this.updateSelection();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
            this.updateSelection();
        } else if (e.key === 'Enter' && this.selectedIndex >= 0) {
            e.preventDefault();
            this.select(this.selectedIndex);
        } else if (e.key === 'Escape') {
            this.hide();
        }
    }

    updateSelection() {
        const items = this.dropdown.querySelectorAll('.autocomplete-item');
        items.forEach((item, i) => {
            if (i === this.selectedIndex) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });
    }

    select(index) {
        const item = this.suggestions[index];
        if (!item) return;

        // Set input value
        if (this.type === 'company') {
            this.input.value = item.name;
        } else {
            this.input.value = item.value;
        }

        // Trigger callback
        if (this.onSelect) {
            this.onSelect(item);
        }

        this.hide();
    }

    hide() {
        this.dropdown.classList.add('hidden');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    destroy() {
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        this.input.removeEventListener('input', this.inputHandler);
        this.input.removeEventListener('keydown', this.keydownHandler);
        this.input.removeEventListener('blur', this.blurHandler);
        this.input.removeEventListener('focus', this.focusHandler);

        if (this.dropdown && this.dropdown.parentNode) {
            this.dropdown.remove();
        }
    }
}


// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.complaintChat = new ComplaintChat();
});
