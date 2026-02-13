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

        // Autocomplete instance
        this.currentAutocomplete = null;
        this.selectedCompanyData = null;

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadState();
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
    }

    /**
     * Determine API version based on current URL
     */
    getApiVersion() {
        return window.location.pathname.startsWith('/v2') ? 'v2' : 'v1';
    }

    /**
     * Get API endpoint with version prefix
     */
    getApiEndpoint(path) {
        const version = this.getApiVersion();
        if (version === 'v2') {
            return `/api/v2${path}`;
        }
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
                this.showInputArea(lastAssistant.input_type || 'options', lastAssistant.options);
            }

            // Show back button if we have history
            this.updateBackButton(data.history.length > 2);

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
        this.updateCharCount();
        this.updateSendButton();

        // Show user message - use displayText if provided, otherwise use message
        const textToShow = displayText || text;
        this.renderMessage('user', textToShow);

        // Hide options
        this.optionsContainer.classList.add('hidden');

        // Show typing indicator
        this.showTyping(true);

        // Prepare request body - always send the actual message (ID) to backend
        const requestBody = { message: text };

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

            // Show assistant response
            this.renderMessage('assistant', data.message);

            // Update step count
            this.stepCount++;
            this.updateProgress();

            // Update input area - pass extra data for sending_results
            this.showInputArea(
                data.input_type || 'options',
                data.options,
                data.current_text,
                {
                    results: data.results,
                    pdfDownloadUrl: data.pdf_download_url
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
            messageDiv.className = `flex items-end gap-3 max-w-[90%] ${animate ? 'animate-fade-in' : ''}`;
            messageDiv.innerHTML = `
                <div class="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-blue-400 shrink-0 flex items-center justify-center">
                    <span class="material-symbols-outlined text-white text-[16px]">smart_toy</span>
                </div>
                <div class="flex flex-col gap-1">
                    <span class="text-xs text-slate-500 dark:text-text-muted ml-1">Юридический помощник</span>
                    <div class="bg-white dark:bg-element-dark p-4 rounded-2xl rounded-bl-none shadow-sm dark:shadow-none border border-slate-100 dark:border-transparent">
                        <div class="text-[15px] leading-relaxed text-slate-700 dark:text-white">${this.formatMessage(content)}</div>
                    </div>
                </div>
            `;
        } else {
            messageDiv.className = `flex items-end gap-3 max-w-[90%] ml-auto ${animate ? 'animate-fade-in' : ''}`;
            messageDiv.innerHTML = `
                <div class="flex flex-col gap-1 items-end">
                    <div class="bg-primary p-4 rounded-2xl rounded-br-none shadow-sm">
                        <div class="text-[15px] leading-relaxed text-white">${this.formatMessage(content)}</div>
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
            this.renderOptions(options);
            this.optionsContainer.classList.remove('hidden');
            // Also show text input for custom answers
            this.messageInput.value = currentText || '';
            this.messageInput.placeholder = 'Или введите свой ответ...';
            this.autoResizeTextarea();
            this.updateCharCount();
            this.updateSendButton();
        } else if (type === 'multiselect' && options && options.length > 0) {
            this.renderMultiselect(options);
            this.optionsContainer.classList.remove('hidden');
        } else if (type === 'textarea' || type === 'text') {
            this.messageInput.value = currentText || '';
            this.messageInput.placeholder = type === 'textarea' ? 'Опишите подробно...' : 'Введите ответ...';
            this.autoResizeTextarea();
            this.updateCharCount();
            this.updateSendButton();
            this.messageInput.focus();
        } else if (type.startsWith('autocomplete_')) {
            // Autocomplete input types
            const acType = type.replace('autocomplete_', '');
            const placeholders = {
                'company': 'Введите ИНН или название организации...',
                'address': 'Начните вводить адрес...',
                'fio': 'Введите ФИО...'
            };

            this.messageInput.value = currentText || '';
            this.messageInput.placeholder = placeholders[acType] || 'Введите...';
            this.autoResizeTextarea();
            this.updateCharCount();
            this.updateSendButton();

            // Show mandatory selection indicator
            const labels = {
                'company': 'Выберите организацию из списка',
                'address': 'Выберите адрес из подсказок',
                'fio': 'Выберите ФИО из подсказок'
            };

            // Add indicator above input
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

            // Mark that we need autocomplete selection
            this.requiresAutocompleteSelection = true;
            this.autocompleteType = acType;

            // Initialize autocomplete
            this.currentAutocomplete = new Autocomplete(
                this.messageInput,
                acType,
                (item) => this.onAutocompleteSelect(item, acType)
            );

            this.messageInput.focus();
        } else if (type === 'sending_results' && extraData) {
            // Render sending results with action buttons
            this.renderSendingResults(extraData.results, extraData.pdfDownloadUrl);
            this.optionsContainer.classList.remove('hidden');
        } else {
            this.requiresAutocompleteSelection = false;
        }
    }

    renderSendingResults(results, pdfDownloadUrl) {
        const container = document.createElement('div');
        container.className = 'space-y-4 max-h-[60vh] overflow-y-auto pr-2';

        // Recipient cards (PDF button is now inside each card)
        if (results && results.length > 0) {
            const recipientsDiv = document.createElement('div');
            recipientsDiv.className = 'space-y-4';

            results.forEach((result, index) => {
                const card = document.createElement('div');
                card.className = 'p-5 bg-white dark:bg-element-dark rounded-xl border border-slate-200 dark:border-slate-700/50 shadow-sm';

                // Header with PDF button
                const header = document.createElement('div');
                header.className = 'flex items-center justify-between mb-3 pb-3 border-b border-slate-200 dark:border-slate-700';

                const headerText = document.createElement('div');
                headerText.className = 'flex items-center gap-2 font-bold text-lg text-slate-900 dark:text-white';
                headerText.innerHTML = `<span class="text-primary">${index + 1}.</span> ${this.escapeHtml(result.recipient_name)}`;
                header.appendChild(headerText);

                // PDF download button for this recipient
                const pdfBtn = document.createElement('a');
                const recipientId = result.recipient_id || result.id || '';
                pdfBtn.href = `/api/v2/download-pdf?recipient_id=${encodeURIComponent(recipientId)}`;
                pdfBtn.className = 'flex items-center gap-1 px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white text-sm rounded-lg transition-colors';
                pdfBtn.innerHTML = '<span class="material-symbols-outlined text-base">picture_as_pdf</span> PDF';
                pdfBtn.title = 'Скачать PDF для этого получателя';
                header.appendChild(pdfBtn);

                card.appendChild(header);

                // Contact info section
                const contactSection = document.createElement('div');
                contactSection.className = 'mb-4 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg space-y-2';

                // Address
                if (result.address) {
                    const addressRow = document.createElement('div');
                    addressRow.className = 'flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300';
                    addressRow.innerHTML = `<span class="material-symbols-outlined text-base text-slate-400 shrink-0">location_on</span><span>${this.escapeHtml(result.address)}</span>`;
                    contactSection.appendChild(addressRow);
                }

                // Phone
                if (result.phone) {
                    const phoneRow = document.createElement('div');
                    phoneRow.className = 'flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300';
                    phoneRow.innerHTML = `<span class="material-symbols-outlined text-base text-slate-400">call</span><a href="tel:${result.phone}" class="hover:text-primary">${this.escapeHtml(result.phone)}</a>`;
                    contactSection.appendChild(phoneRow);
                }

                // Working hours
                if (result.working_hours) {
                    const hoursRow = document.createElement('div');
                    hoursRow.className = 'flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400';
                    hoursRow.innerHTML = `<span class="material-symbols-outlined text-base text-slate-400">schedule</span><span>${this.escapeHtml(result.working_hours)}</span>`;
                    contactSection.appendChild(hoursRow);
                }

                // Processing time
                if (result.processing_time) {
                    const timeRow = document.createElement('div');
                    timeRow.className = 'flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200';
                    timeRow.innerHTML = `<span class="material-symbols-outlined text-base text-amber-500">timer</span><span>Срок ответа: ${this.escapeHtml(result.processing_time)}</span>`;
                    contactSection.appendChild(timeRow);
                }

                if (contactSection.children.length > 0) {
                    card.appendChild(contactSection);
                }

                // Submission methods grid
                const methodsGrid = document.createElement('div');
                methodsGrid.className = 'grid grid-cols-1 md:grid-cols-2 gap-3';

                // Portal column (priority)
                const portalCol = document.createElement('div');
                portalCol.className = 'p-4 rounded-xl border-2 ' + (result.website ? 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800' : 'bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700');

                const portalHeader = document.createElement('div');
                portalHeader.className = 'flex items-center gap-2 font-bold text-purple-700 dark:text-purple-400 mb-3';
                portalHeader.innerHTML = '<span class="material-symbols-outlined text-lg">language</span> Портал (рекомендуется)';
                portalCol.appendChild(portalHeader);

                if (result.website) {
                    const portalInfo = document.createElement('div');
                    portalInfo.className = 'text-sm text-slate-600 dark:text-slate-300 space-y-2 mb-4';

                    // Auth requirements with explanation
                    let authHtml = '';
                    if (result.auth_required) {
                        authHtml = `<div class="flex items-start gap-2 p-2 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
                            <span class="material-symbols-outlined text-base text-amber-600 shrink-0 mt-0.5">key</span>
                            <div>
                                <div class="font-medium text-amber-700 dark:text-amber-400">Требуется авторизация</div>
                                <div class="text-xs text-amber-600 dark:text-amber-500">${this.escapeHtml(result.auth_required)}</div>
                            </div>
                        </div>`;
                    } else {
                        authHtml = `<div class="flex items-center gap-2 text-green-600 dark:text-green-400">
                            <span class="material-symbols-outlined text-base">check_circle</span>
                            <span>Часто без регистрации</span>
                        </div>`;
                    }

                    portalInfo.innerHTML = `
                        <div class="flex items-start gap-2">
                            <span class="text-green-500 shrink-0">✓</span>
                            <div><strong>Официальный канал</strong> — обращение регистрируется автоматически</div>
                        </div>
                        <div class="flex items-start gap-2">
                            <span class="text-green-500 shrink-0">✓</span>
                            <div><strong>Отслеживание статуса</strong> — можно проверить ход рассмотрения</div>
                        </div>
                        <div class="flex items-start gap-2">
                            <span class="text-green-500 shrink-0">✓</span>
                            <div><strong>Гарантированный ответ</strong> — обязаны ответить в срок по закону</div>
                        </div>
                        ${authHtml}
                    `;
                    portalCol.appendChild(portalInfo);

                    if (result.portal_name) {
                        const portalName = document.createElement('div');
                        portalName.className = 'text-xs text-slate-500 dark:text-slate-400 mb-2';
                        portalName.textContent = `Портал: ${result.portal_name}`;
                        portalCol.appendChild(portalName);
                    }

                    const portalBtn = document.createElement('a');
                    portalBtn.href = result.website;
                    portalBtn.target = '_blank';
                    portalBtn.rel = 'noopener noreferrer';
                    portalBtn.className = 'w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors font-semibold';
                    portalBtn.innerHTML = '<span class="material-symbols-outlined">open_in_new</span> Перейти на портал';
                    portalCol.appendChild(portalBtn);
                } else {
                    const noPortal = document.createElement('div');
                    noPortal.className = 'text-sm text-slate-500 italic';
                    noPortal.innerHTML = `
                        <div class="flex items-center gap-2 mb-2"><span class="text-slate-400">✗</span> Портал не найден</div>
                        <div class="text-slate-400">Электронная приёмная недоступна. Используйте другие способы.</div>
                    `;
                    portalCol.appendChild(noPortal);
                }
                methodsGrid.appendChild(portalCol);

                // Email column
                const emailCol = document.createElement('div');
                emailCol.className = 'p-4 rounded-xl border-2 ' + (result.email ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' : 'bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700');

                const emailHeader = document.createElement('div');
                emailHeader.className = 'flex items-center gap-2 font-bold text-green-700 dark:text-green-400 mb-3';
                emailHeader.innerHTML = '<span class="material-symbols-outlined text-lg">mail</span> Email';
                emailCol.appendChild(emailHeader);

                if (result.email) {
                    const emailInfo = document.createElement('div');
                    emailInfo.className = 'text-sm text-slate-600 dark:text-slate-300 space-y-2 mb-4';
                    emailInfo.innerHTML = `
                        <div class="flex items-start gap-2">
                            <span class="text-green-500 shrink-0">✓</span>
                            <div><strong>Быстрая отправка</strong> — не нужно регистрироваться</div>
                        </div>
                        <div class="flex items-start gap-2">
                            <span class="text-green-500 shrink-0">✓</span>
                            <div><strong>Вложения</strong> — можно прикрепить PDF и документы</div>
                        </div>
                        <div class="flex items-start gap-2 text-amber-600 dark:text-amber-400">
                            <span class="shrink-0">⚠</span>
                            <div>Нет автоматической регистрации — сохраните копию письма</div>
                        </div>
                    `;
                    emailCol.appendChild(emailInfo);

                    const emailAddr = document.createElement('div');
                    emailAddr.className = 'text-xs text-slate-500 dark:text-slate-400 mb-2 font-mono';
                    emailAddr.textContent = result.email;
                    emailCol.appendChild(emailAddr);

                    const emailBtn = document.createElement('button');
                    emailBtn.className = 'w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors font-semibold';
                    emailBtn.innerHTML = '<span class="material-symbols-outlined">send</span> Написать письмо';
                    emailBtn.addEventListener('click', () => this.showEmailModal(result));
                    emailCol.appendChild(emailBtn);
                } else {
                    const noEmail = document.createElement('div');
                    noEmail.className = 'text-sm text-slate-500 italic';
                    noEmail.innerHTML = `
                        <div class="flex items-center gap-2 mb-2"><span class="text-slate-400">✗</span> Email не найден</div>
                        <div class="text-slate-400">Орган не публикует email для обращений. Используйте портал.</div>
                    `;
                    emailCol.appendChild(noEmail);
                }
                methodsGrid.appendChild(emailCol);

                card.appendChild(methodsGrid);

                // Documents needed section
                if (result.documents_needed && result.documents_needed.length > 0) {
                    const docsSection = document.createElement('div');
                    docsSection.className = 'mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800';
                    docsSection.innerHTML = `
                        <div class="flex items-center gap-2 font-semibold text-blue-700 dark:text-blue-400 mb-2">
                            <span class="material-symbols-outlined text-base">description</span>
                            Приложите к обращению (если есть)
                        </div>
                        <ul class="text-sm text-blue-600 dark:text-blue-300 list-disc list-inside space-y-1">
                            ${result.documents_needed.map(doc => `<li>${this.escapeHtml(doc)}</li>`).join('')}
                        </ul>
                    `;
                    card.appendChild(docsSection);
                }

                // Practical tip
                if (result.tips) {
                    const tipSection = document.createElement('div');
                    tipSection.className = 'mt-4 p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg border border-emerald-200 dark:border-emerald-800';
                    tipSection.innerHTML = `
                        <div class="flex items-start gap-2 text-sm text-emerald-700 dark:text-emerald-300">
                            <span class="material-symbols-outlined text-lg text-emerald-500 shrink-0">lightbulb</span>
                            <div><strong>Совет:</strong> ${this.escapeHtml(result.tips)}</div>
                        </div>
                    `;
                    card.appendChild(tipSection);
                }

                // PDF download reminder
                const pdfTip = document.createElement('div');
                pdfTip.className = 'mt-4 pt-3 border-t border-slate-200 dark:border-slate-700 text-xs text-slate-500 dark:text-slate-400 flex items-start gap-2';
                pdfTip.innerHTML = `
                    <span class="material-symbols-outlined text-sm text-primary shrink-0">picture_as_pdf</span>
                    <span>Скачайте PDF и приложите к письму или загрузите на портал — так ваше обращение будет оформлено профессионально</span>
                `;
                card.appendChild(pdfTip);

                recipientsDiv.appendChild(card);
            });

            container.appendChild(recipientsDiv);
        }

        // New complaint button
        const newBtn = document.createElement('button');
        newBtn.className = 'flex items-center justify-center gap-2 w-full p-3 mt-4 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-xl transition-colors';
        newBtn.innerHTML = `
            <span class="material-symbols-outlined">add</span>
            <span>📝 Новая жалоба</span>
        `;
        newBtn.addEventListener('click', () => this.restart());
        container.appendChild(newBtn);

        this.optionsContainer.appendChild(container);
    }

    onAutocompleteSelect(item, type) {
        // Store selected data
        if (type === 'company') {
            this.selectedCompanyData = item;
            this.showToast(`✓ ${item.name}`, 'success');
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

    renderOptions(options) {
        const grid = document.createElement('div');
        grid.className = 'grid grid-cols-1 sm:grid-cols-2 gap-3';

        const icons = {
            'жкх': 'apartment',
            'работодатель': 'badge',
            'магазин': 'storefront',
            'госорган': 'account_balance',
            'банк': 'account_balance_wallet',
            'соседи': 'groups',
            'другое': 'more_horiz',
            'default': 'arrow_forward'
        };

        options.forEach(option => {
            const btn = document.createElement('button');
            btn.className = 'group flex items-center justify-between p-4 bg-white dark:bg-element-dark hover:bg-primary/5 dark:hover:bg-element-dark/80 border border-slate-200 dark:border-slate-700/50 hover:border-primary dark:hover:border-primary rounded-full transition-all duration-200 shadow-sm active:scale-[0.98]';

            const textLower = option.text.toLowerCase();
            let icon = icons['default'];
            for (const [key, value] of Object.entries(icons)) {
                if (textLower.includes(key)) {
                    icon = value;
                    break;
                }
            }

            btn.innerHTML = `
                <span class="font-medium text-sm pl-2 text-slate-900 dark:text-white">${option.text}</span>
                <span class="material-symbols-outlined text-slate-400 group-hover:text-primary transition-colors text-[20px] pr-1">${icon}</span>
            `;
            btn.dataset.id = option.id;

            btn.addEventListener('click', () => {
                // Send option.id to backend, but show option.text in chat
                const messageToSend = option.id || option.text;
                const displayText = option.text;
                this.sendMessage(messageToSend, displayText);
            });

            grid.appendChild(btn);
        });

        this.optionsContainer.appendChild(grid);
    }

    renderMultiselect(options) {
        const container = document.createElement('div');
        container.className = 'flex flex-col';

        // Header
        const header = document.createElement('div');
        header.className = 'text-sm text-slate-500 dark:text-slate-400 mb-2';
        header.innerHTML = '✓ Выберите одного или нескольких получателей';
        container.appendChild(header);

        // Scrollable options list
        const optionsList = document.createElement('div');
        optionsList.className = 'space-y-3 overflow-y-auto max-h-[50vh] pr-2';

        // Options list
        options.forEach(option => {
            if (option.id === 'custom') return; // Skip custom option for now

            const card = document.createElement('label');
            card.className = 'flex items-start gap-3 p-4 bg-white dark:bg-element-dark rounded-xl border border-slate-200 dark:border-slate-700/50 cursor-pointer hover:border-primary/50 transition-all';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = option.id;
            checkbox.className = 'mt-1 w-5 h-5 rounded border-slate-300 text-primary focus:ring-primary';
            checkbox.addEventListener('change', () => {
                if (checkbox.checked) {
                    this.selectedOptions.add(option.id);
                    card.classList.add('border-primary', 'bg-primary/5');
                } else {
                    this.selectedOptions.delete(option.id);
                    card.classList.remove('border-primary', 'bg-primary/5');
                }
                this.updateMultiselectSubmit();
            });

            const content = document.createElement('div');
            content.className = 'flex-1';

            // Title row with level badge
            const titleRow = document.createElement('div');
            titleRow.className = 'flex items-center gap-2 flex-wrap';

            const title = document.createElement('span');
            title.className = 'font-semibold text-slate-900 dark:text-white';
            title.textContent = option.text;
            titleRow.appendChild(title);

            // Jurisdiction level badge
            if (option.level) {
                const levelBadge = document.createElement('span');
                const level = option.level.toLowerCase();
                const levelStyles = {
                    'местный': { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400', icon: '🏠' },
                    'региональный': { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-400', icon: '🏛️' },
                    'федеральный': { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-700 dark:text-purple-400', icon: '🏛️' }
                };
                const style = levelStyles[level] || { bg: 'bg-slate-100', text: 'text-slate-700', icon: '📍' };
                levelBadge.className = `text-xs px-2 py-0.5 rounded-full ${style.bg} ${style.text}`;
                levelBadge.textContent = `${style.icon} ${option.level}`;
                titleRow.appendChild(levelBadge);
            }

            // Effectiveness indicator
            if (option.effectiveness) {
                const effBadge = document.createElement('span');
                const effStyles = {
                    'high': { bg: 'bg-emerald-100 dark:bg-emerald-900/30', text: 'text-emerald-700 dark:text-emerald-400', label: '✓ рекомендуется' },
                    'medium': { bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-700 dark:text-amber-400', label: '~ стандартный' },
                    'low': { bg: 'bg-slate-100 dark:bg-slate-800', text: 'text-slate-500', label: '⚠ крайняя мера' }
                };
                const style = effStyles[option.effectiveness] || effStyles['medium'];
                effBadge.className = `text-xs px-2 py-0.5 rounded-full ${style.bg} ${style.text}`;
                effBadge.textContent = style.label;
                titleRow.appendChild(effBadge);
            }

            content.appendChild(titleRow);

            // Reason/description
            if (option.reason || option.description) {
                const desc = document.createElement('div');
                desc.className = 'text-sm text-slate-500 dark:text-slate-400 mt-1';
                desc.textContent = option.reason || option.description;
                content.appendChild(desc);
            }

            // Contact info section
            const contactsSection = document.createElement('div');
            contactsSection.className = 'mt-3 space-y-1 text-sm';

            if (option.address) {
                const addressRow = document.createElement('div');
                addressRow.className = 'flex items-start gap-2 text-slate-600 dark:text-slate-300';
                addressRow.innerHTML = `<span class="shrink-0">📍</span><span>${option.address}</span>`;
                contactsSection.appendChild(addressRow);
            }

            if (option.phone) {
                const phoneRow = document.createElement('div');
                phoneRow.className = 'flex items-center gap-2 text-slate-600 dark:text-slate-300';
                phoneRow.innerHTML = `<span>📞</span><a href="tel:${option.phone}" class="hover:text-primary">${option.phone}</a>`;
                contactsSection.appendChild(phoneRow);
            }

            if (option.working_hours) {
                const hoursRow = document.createElement('div');
                hoursRow.className = 'flex items-center gap-2 text-slate-500 dark:text-slate-400';
                hoursRow.innerHTML = `<span>🕐</span><span>${option.working_hours}</span>`;
                contactsSection.appendChild(hoursRow);
            }

            if (contactsSection.children.length > 0) {
                content.appendChild(contactsSection);
            }

            // Submission methods badges
            const badges = document.createElement('div');
            badges.className = 'flex flex-wrap gap-2 mt-3';

            if (option.submission_methods && option.submission_methods.length > 0) {
                option.submission_methods.forEach(method => {
                    const badge = document.createElement('span');
                    badge.className = 'text-xs px-2 py-1 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-full';
                    const icons = { 'Портал': '🌐', 'Email': '📧', 'Личный приём': '👤', 'Почта': '✉️', 'Почта России': '✉️' };
                    const icon = icons[method] || '📋';
                    badge.textContent = `${icon} ${method}`;
                    badges.appendChild(badge);
                });
            }

            if (badges.children.length > 0) {
                content.appendChild(badges);
            }

            // Requirements and info section
            const infoSection = document.createElement('div');
            infoSection.className = 'mt-3 space-y-2 text-sm';

            if (option.auth_required) {
                const authRow = document.createElement('div');
                authRow.className = 'flex items-start gap-2 text-amber-700 dark:text-amber-400';
                authRow.innerHTML = `<span class="shrink-0">🔐</span><span>${option.auth_required}</span>`;
                infoSection.appendChild(authRow);
            }

            if (option.processing_time) {
                const timeRow = document.createElement('div');
                timeRow.className = 'flex items-center gap-2 text-slate-500 dark:text-slate-400';
                timeRow.innerHTML = `<span>⏱️</span><span>Срок ответа: ${option.processing_time}</span>`;
                infoSection.appendChild(timeRow);
            }

            if (option.documents_needed && option.documents_needed.length > 0) {
                const docsRow = document.createElement('div');
                docsRow.className = 'flex items-start gap-2 text-slate-500 dark:text-slate-400';
                docsRow.innerHTML = `<span class="shrink-0">📄</span><span>Могут понадобиться: ${option.documents_needed.join(', ')}</span>`;
                infoSection.appendChild(docsRow);
            }

            if (infoSection.children.length > 0) {
                content.appendChild(infoSection);
            }

            // Tip / recommendation
            if (option.tips) {
                const tipRow = document.createElement('div');
                tipRow.className = 'mt-3 p-2 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg text-sm text-emerald-700 dark:text-emerald-300';
                tipRow.innerHTML = `<span>💡</span> ${option.tips}`;
                content.appendChild(tipRow);
            }

            // Portal link button
            if (option.website) {
                const portalLink = document.createElement('a');
                portalLink.href = option.website;
                portalLink.target = '_blank';
                portalLink.className = 'mt-3 inline-flex items-center gap-1 text-sm text-primary hover:text-primary-hover transition-colors';
                portalLink.innerHTML = `🌐 ${option.portal_name || 'Перейти на портал'} <span class="text-xs">↗</span>`;
                content.appendChild(portalLink);
            }

            card.appendChild(checkbox);
            card.appendChild(content);
            optionsList.appendChild(card);
        });

        // Add scrollable list to container
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
        if (this.requiresAutocompleteSelection && hasText) {
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

    showEmailModal(result) {
        // Extract email data from result
        const email = result.email || '';
        const recipientName = result.recipient_name || 'Получатель';
        const mailtoLink = result.mailto_link || '';

        // Parse mailto to get subject and body
        let subject = 'Жалоба';
        let body = '';
        try {
            const mailtoUrl = new URL(mailtoLink);
            subject = mailtoUrl.searchParams.get('subject') || 'Жалоба';
            body = mailtoUrl.searchParams.get('body') || '';
        } catch (e) {
            console.log('Could not parse mailto');
        }

        // Encode for URLs
        const encodedSubject = encodeURIComponent(subject);
        // Ограничиваем тело для webmail ссылок (лимит URL ~2000 символов)
        const shortBody = body.length > 500
            ? body.substring(0, 500) + '\n\n[Полный текст в прикреплённом PDF]'
            : body;
        const encodedBody = encodeURIComponent(shortBody);
        const encodedEmail = encodeURIComponent(email);

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
                                class="flex-1 p-3 bg-slate-100 dark:bg-element-dark rounded-lg text-slate-900 dark:text-white font-mono text-sm">
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
                                class="flex-1 p-3 bg-slate-100 dark:bg-element-dark rounded-lg text-slate-900 dark:text-white text-sm">
                            <button id="copy-subject" class="p-3 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 rounded-lg transition-colors" title="Копировать">
                                <span class="material-symbols-outlined text-slate-700 dark:text-slate-300">content_copy</span>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Body preview -->
                    <div class="space-y-1">
                        <label class="text-sm font-medium text-slate-500 dark:text-slate-400">Текст письма</label>
                        <div class="relative">
                            <textarea readonly 
                                class="w-full p-3 bg-slate-100 dark:bg-element-dark rounded-lg text-slate-900 dark:text-white text-sm h-32 resize-none">${this.escapeHtml(body.substring(0, 500))}${body.length > 500 ? '...' : ''}</textarea>
                            <button id="copy-body" class="absolute top-2 right-2 p-2 bg-white dark:bg-slate-600 hover:bg-slate-50 dark:hover:bg-slate-500 rounded-lg shadow-sm transition-colors" title="Копировать всё">
                                <span class="material-symbols-outlined text-slate-700 dark:text-slate-300 text-sm">content_copy</span>
                            </button>
                        </div>
                    </div>
                    
                    <!-- PDF reminder -->
                    <div class="flex items-center gap-3 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                        <span class="text-amber-600 dark:text-amber-400">📎</span>
                        <span class="text-sm text-amber-800 dark:text-amber-300">Не забудьте прикрепить PDF-файл жалобы!</span>
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

        // Store body text for copying
        const fullBody = body;

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
            navigator.clipboard.writeText(fullBody);
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
            // For v2 use /reset, for v1 use /restart
            const endpoint = this.getApiVersion() === 'v2'
                ? '/api/v2/reset'
                : '/api/restart';
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
