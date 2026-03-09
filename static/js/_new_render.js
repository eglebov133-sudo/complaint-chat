renderSendingResults(results, isPaid = true) {
    const container = document.createElement('div');
    container.className = 'space-y-3 max-h-[70vh] overflow-y-auto pr-1';

    // Payment banner
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
                            <a href="/tariffs" class="inline-flex items-center gap-1 px-2 py-1.5 text-amber-600 dark:text-amber-400 text-[11px] hover:underline">Все тарифы →</a>
                        </div>
                    </div>
                </div>`;
        container.appendChild(banner);
    }

    // Recipient cards — single column, rich layout
    if (results && results.length > 0) {
        results.forEach((result, index) => {
            const card = document.createElement('div');
            card.className = 'bg-white dark:bg-surface-lighter rounded-xl border border-slate-200 dark:border-white/[0.06] overflow-hidden';

            // Header
            let headerHtml = `<div class="p-3 pb-2 border-b border-slate-100 dark:border-white/[0.04]">
                    <div class="flex items-start justify-between gap-2">
                        <div class="flex items-center gap-2 min-w-0">
                            <span class="text-[15px] shrink-0">🏛️</span>
                            <span class="font-bold text-[12px] text-slate-800 dark:text-white leading-snug">${this.escapeHtml(result.recipient_name)}</span>
                        </div>
                        <span class="text-[9px] text-slate-400 shrink-0">${index + 1}/${results.length}</span>
                    </div>
                </div>`;

            // Contacts
            let contactHtml = '<div class="px-3 pt-2 pb-1 space-y-1 text-[11px] text-slate-600 dark:text-slate-300">';
            if (result.address) contactHtml += `<div class="flex items-start gap-1.5"><span class="material-symbols-outlined text-[13px] text-slate-400 shrink-0 mt-px">location_on</span><span class="leading-snug">${this.escapeHtml(result.address)}</span></div>`;
            if (result.phone) contactHtml += `<div class="flex items-center gap-1.5"><span class="material-symbols-outlined text-[13px] text-slate-400">call</span><a href="tel:${result.phone}" class="hover:text-primary transition">${this.escapeHtml(result.phone)}</a></div>`;
            if (result.working_hours) contactHtml += `<div class="flex items-center gap-1.5"><span class="material-symbols-outlined text-[13px] text-slate-400">schedule</span>${this.escapeHtml(result.working_hours)}</div>`;
            if (result.processing_time) contactHtml += `<div class="flex items-center gap-1.5"><span class="material-symbols-outlined text-[13px] text-amber-500">timer</span><b class="text-amber-700 dark:text-amber-400">Срок ответа: ${this.escapeHtml(result.processing_time)}</b></div>`;
            contactHtml += '</div>';

            // Recommendation tip
            let tipText = '', tipIcon = '💡';
            if (result.website && result.email) {
                tipText = '<b>Рекомендация:</b> Подайте жалобу через <b>портал</b> — это самый быстрый способ, обращение регистрируется автоматически. Дополнительно продублируйте по <b>email</b> для надёжности.';
            } else if (result.website) {
                tipText = '<b>Рекомендация:</b> Подайте через <b>интернет-приёмную</b> — обращение зарегистрируется моментально. Сохраните номер входящего.';
            } else if (result.email) {
                tipText = '<b>Рекомендация:</b> Отправьте жалобу по <b>email</b>. Прикрепите PDF-файл к письму. Электронное письмо имеет юридическую силу.';
            } else if (result.address) {
                tipText = '<b>Рекомендация:</b> Направьте жалобу <b>почтой России</b> заказным письмом с уведомлением. Сохраните квитанцию.';
                tipIcon = '📮';
            } else {
                tipText = '<b>Совет:</b> Уточните актуальные контакты на официальном сайте ведомства.';
                tipIcon = 'ℹ️';
            }
            const tipHtml = `<div class="mx-3 mb-2 p-2 rounded-md bg-blue-50 dark:bg-blue-900/15 border border-blue-100 dark:border-blue-800/30"><div class="flex items-start gap-1.5 text-[10px] text-blue-800 dark:text-blue-300 leading-snug"><span class="shrink-0">${tipIcon}</span><span>${tipText}</span></div></div>`;

            // Channel blocks with instructions
            let channelsHtml = '<div class="px-3 pb-2 space-y-2">';

            // Portal channel
            if (result.website) {
                if (isPaid) {
                    channelsHtml += `<div class="rounded-lg border border-purple-200 dark:border-purple-800/40 overflow-hidden">
                            <a href="${this.escapeHtml(result.website)}" target="_blank" rel="noopener" class="portal-link-${index} flex items-center gap-2 p-2 bg-purple-50 dark:bg-purple-900/20 hover:bg-purple-100 dark:hover:bg-purple-900/30 transition-colors">
                                <span class="material-symbols-outlined text-purple-600 dark:text-purple-400 text-[15px]">language</span>
                                <div class="flex-1 min-w-0">
                                    <div class="font-semibold text-[11px] text-purple-800 dark:text-purple-300">${result.portal_name || 'Интернет-приёмная'}</div>
                                    <div class="text-[9px] text-purple-500 dark:text-purple-400 truncate">${this.escapeHtml(result.website)}</div>
                                </div>
                                <span class="material-symbols-outlined text-purple-400 text-[13px]">open_in_new</span>
                            </a>
                            <div class="px-2 py-1.5 text-[10px] text-slate-500 dark:text-slate-400 leading-snug border-t border-purple-100 dark:border-purple-800/30">
                                📋 Откройте портал → Найдите «Обращения граждан» → Заполните форму → Прикрепите PDF → Сохраните номер
                            </div>
                        </div>`;
                } else {
                    channelsHtml += `<div class="rounded-lg border border-slate-200 dark:border-slate-700 p-2 opacity-60"><div class="flex items-center gap-2 text-[11px] text-slate-500"><span class="material-symbols-outlined text-[15px]">lock</span>Портал — доступен на платном тарифе</div></div>`;
                }
            }

            // Email channel
            if (result.email) {
                if (isPaid) {
                    channelsHtml += `<div class="rounded-lg border border-green-200 dark:border-green-800/40 overflow-hidden">
                            <button class="email-btn-${index} w-full flex items-center gap-2 p-2 bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/30 transition-colors text-left">
                                <span class="material-symbols-outlined text-green-600 dark:text-green-400 text-[15px]">mail</span>
                                <div class="flex-1 min-w-0">
                                    <div class="font-semibold text-[11px] text-green-800 dark:text-green-300">Отправить по Email</div>
                                    <div class="text-[9px] text-green-500 dark:text-green-400 truncate">${this.escapeHtml(result.email)}</div>
                                </div>
                                <span class="material-symbols-outlined text-green-400 text-[13px]">arrow_forward</span>
                            </button>
                            <div class="px-2 py-1.5 text-[10px] text-slate-500 dark:text-slate-400 leading-snug border-t border-green-100 dark:border-green-800/30">
                                ✉️ Скачайте PDF → Нажмите «Email» → Выберите почтовый сервис → Прикрепите PDF → Отправьте
                            </div>
                        </div>`;
                } else {
                    channelsHtml += `<div class="rounded-lg border border-slate-200 dark:border-slate-700 p-2 opacity-60"><div class="flex items-center gap-2 text-[11px] text-slate-500"><span class="material-symbols-outlined text-[15px]">lock</span>Email — доступен на платном тарифе</div></div>`;
                }
            }

            // Phone tip
            if (result.phone) {
                channelsHtml += `<div class="rounded-lg border border-slate-200 dark:border-slate-700 p-2"><div class="flex items-start gap-1.5 text-[10px] text-slate-500 dark:text-slate-400 leading-snug"><span class="shrink-0">📞</span><span>Позвоните по телефону <b>${this.escapeHtml(result.phone)}</b>${result.working_hours ? ' (' + this.escapeHtml(result.working_hours) + ')' : ''} — уточните, получена ли жалоба, и запросите входящий номер</span></div></div>`;
            }

            // Auth warning
            if (result.auth_required) {
                channelsHtml += `<div class="flex items-center gap-1.5 p-2 rounded-lg bg-amber-50 dark:bg-amber-900/15 border border-amber-200 dark:border-amber-800/30 text-[10px] text-amber-700 dark:text-amber-400"><span class="material-symbols-outlined text-[13px]">key</span> ${this.escapeHtml(result.auth_required)}</div>`;
            }

            // No channels fallback
            if (!result.website && !result.email) {
                channelsHtml += '<div class="p-2 text-[10px] text-slate-400 italic text-center">Электронные каналы не найдены — направьте почтой по указанному адресу</div>';
            }
            channelsHtml += '</div>';

            // Download buttons
            let dlHtml = '<div class="flex gap-2 px-3 pb-3">';
            if (isPaid) {
                dlHtml += `<button class="pdf-btn-${index} flex-1 flex items-center justify-center gap-1 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-[11px] font-semibold transition-colors cursor-pointer"><span class="material-symbols-outlined text-[14px]">picture_as_pdf</span> Скачать PDF</button>`;
                dlHtml += `<button class="doc-btn-${index} flex-1 flex items-center justify-center gap-1 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-[11px] font-semibold transition-colors cursor-pointer"><span class="material-symbols-outlined text-[14px]">description</span> Скачать DOC</button>`;
            } else {
                dlHtml += '<button class="flex-1 flex items-center justify-center gap-1 py-2 bg-slate-200 dark:bg-slate-700 text-slate-400 rounded-lg text-[11px] cursor-not-allowed"><span class="material-symbols-outlined text-[14px]">lock</span> PDF</button>';
                dlHtml += '<button class="flex-1 flex items-center justify-center gap-1 py-2 bg-slate-200 dark:bg-slate-700 text-slate-400 rounded-lg text-[11px] cursor-not-allowed"><span class="material-symbols-outlined text-[14px]">lock</span> DOC</button>';
            }
            dlHtml += '</div>';

            card.innerHTML = headerHtml + contactHtml + tipHtml + channelsHtml + dlHtml;
            container.appendChild(card);

            // Bind event listeners after DOM insertion
            setTimeout(() => {
                const emailBtn = container.querySelector(`.email-btn-${index}`);
                if (emailBtn) {
                    emailBtn.addEventListener('click', () => {
                        fetch('/api/track', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event: 'email_clicked', meta: { recipient: result.recipient_name, email: result.email } }) });
                        this.showEmailModal(result);
                    });
                }
                const portalLink = container.querySelector(`.portal-link-${index}`);
                if (portalLink) {
                    portalLink.addEventListener('click', () => {
                        fetch('/api/track', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event: 'portal_clicked', meta: { recipient: result.recipient_name, url: result.website } }) });
                    });
                }
                const pdfBtn = container.querySelector(`.pdf-btn-${index}`);
                if (pdfBtn) pdfBtn.addEventListener('click', () => this.downloadDocument('pdf', result));
                const docBtn = container.querySelector(`.doc-btn-${index}`);
                if (docBtn) docBtn.addEventListener('click', () => this.downloadDocument('doc', result));
            }, 50);
        });
    }

    // New complaint button
    const newBtn = document.createElement('button');
    newBtn.className = 'flex items-center justify-center gap-1.5 w-full p-2.5 mt-1 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg transition-colors text-[11px]';
    newBtn.innerHTML = '<span class="material-symbols-outlined text-[16px]">add</span><span>Новая жалоба</span>';
    newBtn.addEventListener('click', () => this.restart());
    container.appendChild(newBtn);

    this.optionsContainer.appendChild(container);
}
