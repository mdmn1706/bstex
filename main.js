/**
 * Основной JavaScript файл для Textile ERP
 */

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация всех компонентов
    initSidebarToggle();
    initModals();
    initForms();
    initTables();
    initNotifications();
    initDatePickers();
    initSelect2();
    initCharts();
});

/**
 * Переключение сайдбара
 */
function initSidebarToggle() {
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    
    if (sidebarToggle && sidebar && mainContent) {
        sidebarToggle.addEventListener('click', function(e) {
            e.preventDefault();
            sidebar.classList.toggle('show');
            mainContent.classList.toggle('main-content-full');
        });
        
        // Закрытие сайдбара при клике вне его на мобильных устройствах
        document.addEventListener('click', function(e) {
            if (window.innerWidth <= 992) {
                if (!sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
                    sidebar.classList.remove('show');
                    mainContent.classList.remove('main-content-full');
                }
            }
        });
    }
}

/**
 * Инициализация модальных окон
 */
function initModals() {
    // Открытие модальных окон
    document.querySelectorAll('[data-toggle="modal"]').forEach(button => {
        button.addEventListener('click', function() {
            const target = this.getAttribute('data-target');
            const modal = document.querySelector(target);
            if (modal) {
                showModal(modal);
            }
        });
    });
    
    // Закрытие модальных окон
    document.querySelectorAll('.modal').forEach(modal => {
        // Кнопка закрытия
        const closeBtn = modal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => hideModal(modal));
        }
        
        // Закрытие по клику вне окна
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                hideModal(this);
            }
        });
        
        // Закрытие по ESC
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                hideModal(modal);
            }
        });
    });
}

function showModal(modal) {
    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
}

function hideModal(modal) {
    modal.classList.remove('show');
    document.body.style.overflow = '';
}

/**
 * Инициализация форм
 */
function initForms() {
    // Валидация форм
    document.querySelectorAll('form[data-validate]').forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
            }
        });
    });
    
    // Подтверждение удаления
    document.querySelectorAll('form[data-confirm]').forEach(form => {
        form.addEventListener('submit', function(e) {
            const message = this.getAttribute('data-confirm-message') || 'Вы уверены?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
    
    // Динамическое добавление полей
    document.querySelectorAll('.btn-add-field').forEach(button => {
        button.addEventListener('click', function() {
            const template = document.querySelector(this.getAttribute('data-template'));
            const container = document.querySelector(this.getAttribute('data-container'));
            
            if (template && container) {
                const clone = template.content.cloneNode(true);
                container.appendChild(clone);
                updateFieldIndexes(container);
            }
        });
    });
    
    // Удаление динамических полей
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('btn-remove-field')) {
            const field = e.target.closest('.dynamic-field');
            if (field) {
                field.remove();
                updateFieldIndexes(field.parentElement);
            }
        }
    });
    
    // Автозаполнение суммы
    document.querySelectorAll('.auto-calculate').forEach(input => {
        input.addEventListener('input', function() {
            calculateTotal(this);
        });
    });
}

function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        field.classList.remove('is-invalid');
        
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
            
            // Показать сообщение об ошибке
            const errorMessage = field.getAttribute('data-error-message') || 'Это поле обязательно для заполнения';
            showToast(errorMessage, 'danger');
        }
    });
    
    return isValid;
}

function updateFieldIndexes(container) {
    const fields = container.querySelectorAll('.dynamic-field');
    fields.forEach((field, index) => {
        field.querySelectorAll('input, select, textarea').forEach(input => {
            const name = input.getAttribute('name');
            if (name) {
                input.setAttribute('name', name.replace(/\[\d+\]/, `[${index}]`));
            }
            
            const id = input.getAttribute('id');
            if (id) {
                input.setAttribute('id', id.replace(/-\d+-/, `-${index}-`));
            }
        });
        
        field.querySelectorAll('label').forEach(label => {
            const forAttr = label.getAttribute('for');
            if (forAttr) {
                label.setAttribute('for', forAttr.replace(/-\d+-/, `-${index}-`));
            }
        });
    });
}

function calculateTotal(input) {
    const row = input.closest('tr');
    if (!row) return;
    
    const price = parseFloat(row.querySelector('[data-price]').value) || 0;
    const quantity = parseFloat(row.querySelector('[data-quantity]').value) || 0;
    const totalField = row.querySelector('[data-total]');
    
    if (totalField) {
        const total = price * quantity;
        totalField.value = total.toFixed(2);
        totalField.textContent = formatCurrency(total);
    }
}

/**
 * Инициализация таблиц
 */
function initTables() {
    // Сортировка таблиц
    document.querySelectorAll('.table-sortable th[data-sort]').forEach(th => {
        th.addEventListener('click', function() {
            const table = this.closest('table');
            const column = this.getAttribute('data-sort');
            const direction = this.getAttribute('data-sort-direction') === 'asc' ? 'desc' : 'asc';
            
            // Сброс сортировки в других колонках
            table.querySelectorAll('th[data-sort]').forEach(otherTh => {
                otherTh.removeAttribute('data-sort-direction');
                otherTh.classList.remove('sort-asc', 'sort-desc');
            });
            
            // Установка направления сортировки
            this.setAttribute('data-sort-direction', direction);
            this.classList.add(direction === 'asc' ? 'sort-asc' : 'sort-desc');
            
            // Сортировка данных
            sortTable(table, column, direction);
        });
    });
    
    // Поиск в таблицах
    document.querySelectorAll('.table-search').forEach(input => {
        input.addEventListener('input', function() {
            const table = document.querySelector(this.getAttribute('data-table'));
            if (table) {
                filterTable(table, this.value);
            }
        });
    });
    
    // Пагинация
    document.querySelectorAll('.page-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const url = this.getAttribute('href');
            if (url) {
                loadTablePage(url);
            }
        });
    });
}

function sortTable(table, column, direction) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        const aValue = a.querySelector(`td[data-column="${column}"]`).textContent.trim();
        const bValue = b.querySelector(`td[data-column="${column}"]`).textContent.trim();
        
        // Попытка числового сравнения
        const aNum = parseFloat(aValue.replace(/[^\d.-]/g, ''));
        const bNum = parseFloat(bValue.replace(/[^\d.-]/g, ''));
        
        if (!isNaN(aNum) && !isNaN(bNum)) {
            return direction === 'asc' ? aNum - bNum : bNum - aNum;
        }
        
        // Строковое сравнение
        return direction === 'asc' 
            ? aValue.localeCompare(bValue)
            : bValue.localeCompare(aValue);
    });
    
    // Перезапись строк в отсортированном порядке
    rows.forEach(row => tbody.appendChild(row));
}

function filterTable(table, query) {
    const rows = table.querySelectorAll('tbody tr');
    const lowerQuery = query.toLowerCase();
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(lowerQuery) ? '' : 'none';
    });
}

async function loadTablePage(url) {
    try {
        const response = await fetch(url);
        const html = await response.text();
        
        // Парсинг HTML и обновление таблицы
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const newTable = doc.querySelector('.table-container');
        
        if (newTable) {
            const oldTable = document.querySelector('.table-container');
            oldTable.parentElement.replaceChild(newTable, oldTable);
            
            // Реинициализация таблицы
            initTables();
            
            // Обновление URL без перезагрузки
            window.history.pushState({}, '', url);
        }
    } catch (error) {
        console.error('Error loading table page:', error);
        showToast('Ошибка загрузки данных', 'danger');
    }
}

/**
 * Инициализация уведомлений
 */
function initNotifications() {
    // Автоматическое скрытие alert'ов
    const alerts = document.querySelectorAll('.alert[data-auto-dismiss]');
    alerts.forEach(alert => {
        const delay = parseInt(alert.getAttribute('data-auto-dismiss')) || 5000;
        setTimeout(() => {
            alert.classList.add('fade-out');
            setTimeout(() => alert.remove(), 300);
        }, delay);
    });
    
    // Уведомления WebSocket (если используется)
    initWebSocketNotifications();
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="toast-content">
            <i class="fas fa-${getToastIcon(type)}"></i>
            <span>${message}</span>
        </div>
        <button class="toast-close">&times;</button>
    `;
    
    const container = document.querySelector('.toast-container') || createToastContainer();
    container.appendChild(toast);
    
    // Анимация появления
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Автоматическое скрытие
    setTimeout(() => hideToast(toast), 5000);
    
    // Закрытие по клику
    toast.querySelector('.toast-close').addEventListener('click', () => hideToast(toast));
    
    return toast;
}

function hideToast(toast) {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
}

function getToastIcon(type) {
    const icons = {
        'success': 'check-circle',
        'danger': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    return icons[type] || 'info-circle';
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
}

function initWebSocketNotifications() {
    // Пример WebSocket для уведомлений
    if (typeof io !== 'undefined') {
        const socket = io();
        
        socket.on('order_created', function(data) {
            if (currentUserCan('view_orders')) {
                showToast(`Создан новый заказ #${data.order_number}`, 'info');
            }
        });
        
        socket.on('order_status_changed', function(data) {
            if (currentUserCan('view_orders')) {
                showToast(`Статус заказа #${data.order_number} изменен на "${data.status}"`, 'warning');
            }
        });
        
        socket.on('deadline_approaching', function(data) {
            if (currentUserCan('view_orders')) {
                showToast(`Заказ #${data.order_number} скоро должен быть сдан!`, 'danger');
            }
        });
    }
}

/**
 * Инициализация календарей
 */
function initDatePickers() {
    if (typeof flatpickr !== 'undefined') {
        document.querySelectorAll('.datepicker').forEach(input => {
            flatpickr(input, {
                dateFormat: 'd.m.Y',
                locale: 'ru',
                altInput: true,
                altFormat: 'd.m.Y',
                allowInput: true
            });
        });
        
        document.querySelectorAll('.datetimepicker').forEach(input => {
            flatpickr(input, {
                enableTime: true,
                dateFormat: 'd.m.Y H:i',
                locale: 'ru',
                altInput: true,
                altFormat: 'd.m.Y H:i',
                allowInput: true
            });
        });
    }
}

/**
 * Инициализация Select2
 */
function initSelect2() {
    if (typeof $ !== 'undefined' && $.fn.select2) {
        $('select.select2').select2({
            theme: 'bootstrap',
            width: '100%',
            language: 'ru'
        });
    }
}

/**
 * Инициализация графиков
 */
function initCharts() {
    if (typeof Chart !== 'undefined') {
        document.querySelectorAll('.chart-container').forEach(container => {
            const canvas = container.querySelector('canvas');
            if (!canvas) return;
            
            const type = container.getAttribute('data-chart-type') || 'line';
            const config = JSON.parse(container.getAttribute('data-chart-config') || '{}');
            
            new Chart(canvas.getContext('2d'), {
                type: type,
                data: config.data || {},
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        }
                    },
                    scales: config.scales || {},
                    ...config.options
                }
            });
        });
    }
}

/**
 * Утилитные функции
 */
function formatCurrency(amount, currency = 'UZS') {
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
    }).format(amount);
}

function formatDate(date, format = 'dd.mm.yyyy') {
    const d = new Date(date);
    const day = d.getDate().toString().padStart(2, '0');
    const month = (d.getMonth() + 1).toString().padStart(2, '0');
    const year = d.getFullYear();
    const hours = d.getHours().toString().padStart(2, '0');
    const minutes = d.getMinutes().toString().padStart(2, '0');
    
    return format
        .replace('dd', day)
        .replace('mm', month)
        .replace('yyyy', year)
        .replace('HH', hours)
        .replace('MM', minutes);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * API функции
 */
async function apiRequest(endpoint, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin'
    };
    
    if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(endpoint, options);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return await response.json();
        }
        
        return await response.text();
    } catch (error) {
        console.error('API request failed:', error);
        showToast(`Ошибка запроса: ${error.message}`, 'danger');
        throw error;
    }
}

/**
 * Проверка прав пользователя
 */
function currentUserCan(permission) {
    const userPermissions = window.currentUserPermissions || {};
    return userPermissions[permission] === true;
}

/**
 * Экспорт данных
 */
function exportToExcel(tableId, filename = 'export.xlsx') {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const workbook = XLSX.utils.table_to_book(table, {sheet: "Sheet1"});
    XLSX.writeFile(workbook, filename);
}

function exportToPDF(elementId, filename = 'export.pdf') {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    html2pdf()
        .from(element)
        .set({
            margin: [10, 10, 10, 10],
            filename: filename,
            image: {type: 'jpeg', quality: 0.98},
            html2canvas: {scale: 2, useCORS: true},
            jsPDF: {unit: 'mm', format: 'a4', orientation: 'portrait'}
        })
        .save();
}

/**
 * Drag and Drop
 */
function initDragAndDrop() {
    const draggables = document.querySelectorAll('[draggable="true"]');
    const dropzones = document.querySelectorAll('[data-dropzone]');
    
    draggables.forEach(draggable => {
        draggable.addEventListener('dragstart', function(e) {
            e.dataTransfer.setData('text/plain', this.id);
            this.classList.add('dragging');
        });
        
        draggable.addEventListener('dragend', function() {
            this.classList.remove('dragging');
        });
    });
    
    dropzones.forEach(zone => {
        zone.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.classList.add('drag-over');
        });
        
        zone.addEventListener('dragleave', function() {
            this.classList.remove('drag-over');
        });
        
        zone.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('drag-over');
            
            const id = e.dataTransfer.getData('text/plain');
            const draggable = document.getElementById(id);
            
            if (draggable && this.contains(draggable)) {
                // Обновление данных через API
                const orderId = draggable.getAttribute('data-order-id');
                const newStatus = this.getAttribute('data-status');
                
                apiRequest(`/orders/${orderId}/status`, 'POST', {status: newStatus})
                    .then(data => {
                        if (data.success) {
                            showToast(data.message, 'success');
                        }
                    });
            }
        });
    });
}

/**
 * Обработчики для специфичных компонентов ERP
 */
// Обновление статуса заказа
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('update-status-btn')) {
        e.preventDefault();
        
        const orderId = e.target.getAttribute('data-order-id');
        const status = e.target.getAttribute('data-status');
        const confirmMessage = e.target.getAttribute('data-confirm');
        
        if (confirmMessage && !confirm(confirmMessage)) {
            return;
        }
        
        updateOrderStatus(orderId, status);
    }
});

async function updateOrderStatus(orderId, status) {
    try {
        const data = await apiRequest(`/orders/${orderId}/update-status`, 'POST', {status: status});
        
        if (data.success) {
            showToast(data.message, 'success');
            
            // Обновление интерфейса
            const statusBadge = document.querySelector(`[data-order-id="${orderId}"] .order-status`);
            if (statusBadge) {
                statusBadge.textContent = data.new_status;
                statusBadge.className = `order-status status-${data.new_status}`;
            }
        }
    } catch (error) {
        showToast('Ошибка при обновлении статуса', 'danger');
    }
}

// Быстрое добавление материала в заказ
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('quick-add-material')) {
        e.preventDefault();
        
        const modal = document.querySelector('#addMaterialModal');
        if (modal) {
            const orderId = e.target.getAttribute('data-order-id');
            modal.querySelector('[name="order_id"]').value = orderId;
            showModal(modal);
        }
    }
});

// Поиск материалов в реальном времени
const materialSearch = document.querySelector('#materialSearch');
if (materialSearch) {
    materialSearch.addEventListener('input', debounce(function() {
        const query = this.value;
        searchMaterials(query);
    }, 300));
}

async function searchMaterials(query) {
    if (query.length < 2) return;
    
    try {
        const data = await apiRequest(`/api/materials?search=${encodeURIComponent(query)}`);
        const resultsContainer = document.querySelector('#materialResults');
        
        if (resultsContainer) {
            resultsContainer.innerHTML = data.map(material => `
                <div class="material-result" data-material-id="${material.id}">
                    <strong>${material.name}</strong>
                    <span class="text-muted">${material.stock} ${material.unit} в наличии</span>
                    <button class="btn btn-sm btn-primary select-material">Выбрать</button>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Error searching materials:', error);
    }
}

// Инициализация при загрузке страницы
window.addEventListener('load', function() {
    // Загрузка статистики для дашборда
    if (document.querySelector('.dashboard')) {
        loadDashboardStats();
    }
    
    // Инициализация перетаскивания для этапов производства
    if (document.querySelector('.production-board')) {
        initDragAndDrop();
    }
});

async function loadDashboardStats() {
    try {
        const data = await apiRequest('/api/dashboard/stats');
        
        // Обновление счетчиков
        if (data.total_orders !== undefined) {
            const counter = document.querySelector('.total-orders-counter');
            if (counter) {
                animateCounter(counter, data.total_orders);
            }
        }
        
        // Обновление графиков
        if (data.chart_data) {
            updateCharts(data.chart_data);
        }
    } catch (error) {
        console.error('Error loading dashboard stats:', error);
    }
}

function animateCounter(element, targetValue, duration = 1000) {
    const startValue = parseInt(element.textContent.replace(/\D/g, '')) || 0;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const currentValue = Math.floor(startValue + (targetValue - startValue) * progress);
        element.textContent = currentValue.toLocaleString('ru-RU');
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

// Глобальные обработчики ошибок
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
    showToast('Произошла ошибка в приложении', 'danger');
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
    showToast('Ошибка выполнения операции', 'danger');
});