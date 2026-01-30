
let authToken = localStorage.getItem('adminToken') || '';
let allRegistrations = [];
let allCourses = [];

// Check if logged in on page load
function checkAuth() {
    if (!authToken) {
        showLoginModal();
        return false;
    }
    return true;
}

function showLoginModal() {
    document.getElementById('loginModal').style.display = 'block';
    setTimeout(() => document.getElementById('loginPassword').focus(), 100);
}

function hideLoginModal() {
    document.getElementById('loginModal').style.display = 'none';
}

function logout() {
    authToken = '';
    localStorage.removeItem('adminToken');
    showLoginModal();
    showToast('已登出', '請重新登入', 'warning');
}

// Handle login form
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const password = document.getElementById('loginPassword').value;

            try {
                const response = await apiFetch('/admin/login', {
                    method: 'POST',
                    body: JSON.stringify({ password })
                });

                const result = await response.json();

                if (response.ok) {
                    authToken = result.token;
                    localStorage.setItem('adminToken', authToken);
                    hideLoginModal();
                    showToast('登入成功！', '歡迎使用後台管理系統', 'success');
                    loadAllData();
                } else {
                    showToast('登入失敗', result.message || '密碼錯誤', 'error');
                    document.getElementById('loginPassword').value = '';
                    document.getElementById('loginPassword').focus();
                }
            } catch (error) {
                console.error('Login error:', error);
                showToast('連線錯誤', '無法連接伺服器', 'error');
            }
        });
    }

    // Load all data if authenticated
    if (checkAuth()) {
        loadAllData();
    }
});

function loadAllData() {
    loadRegistrations();
    loadCourses();
    loadRegistrationTime();
}

// Search functionality
document.getElementById('searchInput').addEventListener('input', function (e) {
    const searchTerm = e.target.value.toLowerCase();
    filterRegistrations(searchTerm);
});

// ============ Registration Time Functions ============
async function loadRegistrationTime() {
    try {
        const response = await apiFetch('/api/settings/registration-time');
        if (response.ok) {
            const data = await response.json();
            document.getElementById('registrationStart').value = data.start || '';
            document.getElementById('registrationEnd').value = data.end || '';
            updateRegistrationStatus(data.start, data.end);
        }
    } catch (error) {
        console.error('Error loading registration time:', error);
    }
}

function updateRegistrationStatus(start, end) {
    const statusDiv = document.getElementById('registrationStatus');
    const now = new Date();
    const startDate = start ? new Date(start) : null;
    const endDate = end ? new Date(end) : null;

    let status = '';
    let bgColor = '';
    let textColor = '';

    if (!startDate || !endDate) {
        status = '⚠️ 尚未設定報名時間';
        bgColor = '#fff3cd';
        textColor = '#856404';
    } else if (now < startDate) {
        const daysLeft = Math.ceil((startDate - now) / (1000 * 60 * 60 * 24));
        status = `⏳ 報名尚未開放（還有 ${daysLeft} 天）`;
        bgColor = '#fff3cd';
        textColor = '#856404';
    } else if (now > endDate) {
        status = '🔒 報名已截止';
        bgColor = '#f8d7da';
        textColor = '#721c24';
    } else {
        status = '✅ 報名開放中';
        bgColor = '#d4edda';
        textColor = '#155724';
    }

    statusDiv.style.display = 'block';
    statusDiv.style.backgroundColor = bgColor;
    statusDiv.style.color = textColor;
    statusDiv.innerHTML = `<strong>${status}</strong>`;
}

async function saveRegistrationTime() {
    const start = document.getElementById('registrationStart').value;
    const end = document.getElementById('registrationEnd').value;

    if (!start || !end) {
        showToast('請設定時間', '請設定開始和結束時間', 'warning');
        return;
    }

    if (new Date(start) >= new Date(end)) {
        showToast('時間設定錯誤', '結束時間必須晚於開始時間', 'warning');
        return;
    }

    try {
        const response = await apiFetch('/admin/settings/registration-time', {
            method: 'POST',
            body: JSON.stringify({ start, end })
        });

        if (response.ok) {
            showToast('設定成功！', '報名時間設定已更新', 'success');
            updateRegistrationStatus(start, end);
        } else {
            const error = await response.json();
            showToast('更新失敗', error.message || '未知錯誤', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('連線錯誤', '伺服器連線錯誤', 'error');
    }
}

// ============ Course Management Functions ============

async function loadCourses() {
    try {
        const response = await apiFetch('/admin/courses');
        if (response.status === 401) {
            showLoginModal();
            return;
        }
        if (response.ok) {
            const data = await response.json();
            allCourses = data.courses;
            displayCourses(allCourses);
        } else {
            console.error('Failed to load courses');
        }
    } catch (error) {
        console.error('Error loading courses:', error);
    }
}

function displayCourses(courses) {
    const tbody = document.getElementById('coursesTableBody');

    if (!courses || courses.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="empty-state">
                    <div>沒有課程資料</div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = courses
        .filter(course => !course.name.includes('教材費')) // 過濾掉教材費
        .map(course => {
            const remainingClass = course.remaining <= 0 ? 'full' :
                course.remaining <= 5 ? 'low' : 'ok';
            const remainingText = course.remaining <= 0 ? '已額滿' : course.remaining;
            const videoBadge = course.video_url ? '<span class="badge badge-success">有</span>' : '<span style="color:#ccc">無</span>';

            return `
            <tr>
                <td><strong>${course.name}</strong></td>
                <td>$${course.price.toLocaleString()}</td>
                <td>${course.sessions || '-'}</td>
                <td>${course.frequency || '-'}</td>
                <td><span class="badge badge-info">${course.used}</span></td>
                <td>
                    <input type="number" 
                           class="capacity-input" 
                           id="capacity-${course.id}" 
                           value="${course.capacity}" 
                           min="0" 
                           max="999">
                </td>
                <td><span class="remaining-badge ${remainingClass}">${remainingText}</span></td>
                <td>${videoBadge}</td>
                <td>
                    <div class="action-btns">
                        <button class="btn btn-primary btn-sm" onclick="updateCapacity(${course.id})">
                            💾
                        </button>
                        <button class="btn btn-secondary btn-sm" onclick="openCourseModal('edit', ${course.id})">
                            ✏️
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="deleteCourse(${course.id}, '${course.name.replace(/'/g, "\\'")}')">🗑️</button>
                    </div>
                </td>
            </tr>
        `;
        }).join('');
}

async function updateCapacity(courseId) {
    const input = document.getElementById(`capacity-${courseId}`);
    const newCapacity = parseInt(input.value);

    if (isNaN(newCapacity) || newCapacity < 0) {
        showToast('輸入錯誤', '請輸入有效的容量數字', 'warning');
        return;
    }

    try {
        const response = await apiFetch(`/admin/course/${courseId}`, {
            method: 'PUT',
            body: JSON.stringify({ capacity: newCapacity })
        });

        if (response.ok) {
            showToast('更新成功！', '容量更新成功', 'success');
            loadCourses(); // Reload to show updated remaining
        } else {
            const error = await response.json();
            showToast('更新失敗', error.message || '未知錯誤', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('連線錯誤', '伺服器連線錯誤', 'error');
    }
}

// ============ Course CRUD Functions ============
let currentEditCourseId = null;

function openCourseModal(mode, courseId = null) {
    const modal = document.getElementById('courseModal');
    const title = document.getElementById('courseModalTitle');
    const form = document.getElementById('courseForm');

    // Reset form
    form.reset();
    document.getElementById('courseCapacity').value = '30';

    if (mode === 'add') {
        title.textContent = '➕ 新增課程';
        currentEditCourseId = null;
        document.getElementById('courseId').value = '';
    } else if (mode === 'edit' && courseId) {
        title.textContent = '✏️ 編輯課程';
        currentEditCourseId = courseId;
        document.getElementById('courseId').value = courseId;

        // Fill form with existing course data
        const course = allCourses.find(c => c.id === courseId);
        if (course) {
            document.getElementById('courseName').value = course.name;
            document.getElementById('coursePrice').value = course.price;
            document.getElementById('courseSessions').value = course.sessions || '';
            document.getElementById('courseFrequency').value = course.frequency || '';
            document.getElementById('courseCapacity').value = course.capacity || 30;
            document.getElementById('courseDescription').value = course.description || '';
            document.getElementById('courseVideoUrl').value = course.video_url || '';
        }
    }

    modal.style.display = 'block';
}

function closeCourseModal() {
    document.getElementById('courseModal').style.display = 'none';
    currentEditCourseId = null;
}

// Form submission handler
document.getElementById('courseForm').addEventListener('submit', async function (e) {
    e.preventDefault();

    const courseData = {
        name: document.getElementById('courseName').value.trim(),
        price: parseInt(document.getElementById('coursePrice').value),
        sessions: document.getElementById('courseSessions').value ? parseInt(document.getElementById('courseSessions').value) : null,
        frequency: document.getElementById('courseFrequency').value.trim(),
        capacity: parseInt(document.getElementById('courseCapacity').value) || 30,
        description: document.getElementById('courseDescription').value.trim(),
        video_url: document.getElementById('courseVideoUrl').value.trim()
    };

    if (!courseData.name || isNaN(courseData.price)) {
        showToast('輸入錯誤', '請填寫課程名稱和價格', 'warning');
        return;
    }

    try {
        let response;
        if (currentEditCourseId) {
            // Update existing course
            response = await apiFetch(`/admin/course/${currentEditCourseId}`, {
                method: 'PUT',
                body: JSON.stringify(courseData)
            });
        } else {
            // Create new course
            response = await apiFetch('/admin/course', {
                method: 'POST',
                body: JSON.stringify(courseData)
            });
        }

        const result = await response.json();

        if (response.ok) {
            showToast('成功！', result.message, 'success');
            closeCourseModal();
            loadCourses();
        } else {
            showToast('操作失敗', result.message || '未知錯誤', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('連線錯誤', '伺服器連線錯誤', 'error');
    }
});

async function deleteCourse(courseId, courseName) {
    showConfirm(
        '確認刪除課程？',
        `確定要刪除「${courseName}」嗎？\n⚠️ 如果該課程有報名記錄，將無法刪除。`,
        async () => {
            try {
                const response = await apiFetch(`/admin/course/${courseId}`, {
                    method: 'DELETE'
                });

                const result = await response.json();

                if (response.ok) {
                    showToast('刪除成功！', result.message, 'success');
                    loadCourses();
                } else {
                    showToast('刪除失敗', result.message || '無法刪除此課程', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('連線錯誤', '伺服器連線錯誤', 'error');
            }
        }
    );
}

// ============ Registration Functions ============
async function loadRegistrations() {
    try {
        const response = await apiFetch('/admin/registrations');
        if (response.ok) {
            const data = await response.json();
            allRegistrations = data.registrations;
            updateStatistics(data.statistics);
            displayRegistrations(allRegistrations);
        } else {
            showError('無法載入資料');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('伺服器連線錯誤');
    }
}

function updateStatistics(stats) {
    document.getElementById('totalRegistrations').textContent = stats.totalRegistrations || 0;
    document.getElementById('totalStudents').textContent = stats.totalStudents || 0;
    document.getElementById('totalCourses').textContent = stats.totalCourseEnrollments || 0;
    document.getElementById('totalSupplies').textContent = stats.totalSupplyOrders || 0;
}

function displayRegistrations(registrations) {
    const tbody = document.getElementById('tableBody');

    if (!registrations || registrations.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <div>目前沒有報名資料</div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = registrations.map(reg => `
        <tr>
            <td><span class="badge badge-info">#${reg.id}</span></td>
            <td><strong>${reg.student_name}</strong></td>
            <td>${reg.class_name || '未指定'}</td>
            <td><span class="badge badge-success">${reg.course_count}</span></td>
            <td><span class="badge badge-success">${reg.supply_count}</span></td>
            <td>
                <div class="toggle-switch ${reg.is_paid ? 'active' : ''}" onclick="togglePayment(${reg.id}, ${reg.is_paid})">
                    <div class="toggle-slider"></div>
                </div>
                <span style="font-size: 12px; color: ${reg.is_paid ? '#2ecc71' : '#95a5a6'}; margin-left: 5px;">
                    ${reg.is_paid ? '已繳費' : '未繳費'}
                </span>
            </td>
            <td>${formatDate(reg.created_at)}</td>
            <td>
                <div class="action-btns">
                    <button class="btn btn-primary btn-sm" onclick="viewDetails(${reg.id})">查看</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteRegistration(${reg.id}, '${reg.student_name}')">刪除</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function filterRegistrations(searchTerm) {
    const filtered = allRegistrations.filter(reg =>
        reg.student_name.toLowerCase().includes(searchTerm) ||
        (reg.class_name && reg.class_name.toLowerCase().includes(searchTerm))
    );
    displayRegistrations(filtered);
}

async function viewDetails(id) {
    try {
        const response = await apiFetch(`/admin/registration/${id}`);
        if (response.ok) {
            const data = await response.json();
            showDetailModal(data);
        } else {
            showToast('載入失敗', '無法載入詳細資料', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('連線錯誤', '伺服器連線錯誤', 'error');
    }
}

function showDetailModal(data) {
    const modalBody = document.getElementById('modalBody');

    const coursesHTML = data.courses.length > 0
        ? `<ul class="course-list">${data.courses.map(c => `<li><span>${c.name}</span><span class="price">$${c.price}</span></li>`).join('')}</ul>`
        : '<p style="color: #7f8c8d;">無</p>';

    const suppliesHTML = data.supplies.length > 0
        ? `<ul class="supply-list">${data.supplies.map(s => `<li><span>${s.name}</span><span class="price">$${s.price}</span></li>`).join('')}</ul>`
        : '<p style="color: #7f8c8d;">無</p>';

    const totalCost = [...data.courses, ...data.supplies].reduce((sum, item) => sum + parseInt(item.price), 0);

    modalBody.innerHTML = `
        <div class="detail-row">
            <div class="detail-label">報名 ID</div>
            <div class="detail-value"><strong>#${data.id}</strong></div>
        </div>
        <div class="detail-row">
            <div class="detail-label">學生姓名</div>
            <div class="detail-value"><strong>${data.student_name}</strong></div>
        </div>
        <div class="detail-row">
            <div class="detail-label">幼兒生日</div>
            <div class="detail-value">${data.birthday || '未提供'}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">班級</div>
            <div class="detail-value">${data.class_name || '未指定'}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">繳費狀態</div>
            <div class="detail-value">
                <span class="badge ${data.is_paid ? 'badge-success' : 'badge-secondary'}">
                    ${data.is_paid ? '已繳費' : '未繳費'}
                </span>
            </div>
        </div>
        <div class="detail-row">
            <div class="detail-label">報名課程</div>
            <div class="detail-value">${coursesHTML}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">訂購用品</div>
            <div class="detail-value">${suppliesHTML}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">總金額</div>
            <div class="detail-value"><strong style="font-size: 20px; color: var(--accent-red);">$${totalCost.toLocaleString()}</strong></div>
        </div>
        <div class="detail-row">
            <div class="detail-label">報名時間</div>
            <div class="detail-value">${formatDate(data.created_at)}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">最後更新</div>
            <div class="detail-value">${formatDate(data.updated_at)}</div>
        </div>
    `;

    document.getElementById('detailModal').style.display = 'block';
}

function closeModal() {
    document.getElementById('detailModal').style.display = 'none';
}

async function deleteRegistration(id, name) {
    showConfirm(
        '確認刪除報名？',
        `確定要刪除 ${name} 的報名資料嗎？\n此操作無法復原！`,
        async () => {
            try {
                const response = await apiFetch(`/admin/registration/${id}`, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    showToast('刪除成功！', '報名資料已刪除', 'success');
                    loadRegistrations();
                } else {
                    showToast('刪除失敗', '無法刪除此資料', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('連線錯誤', '伺服器連線錯誤', 'error');
            }
        }
    );
}

async function togglePayment(id, currentStatus) {
    try {
        const newStatus = !currentStatus;
        const response = await apiFetch(`/admin/registration/${id}/payment`, {
            method: 'PUT',
            body: JSON.stringify({ paid: newStatus })
        });

        if (response.ok) {
            const result = await response.json();
            showToast('更新成功', result.message, 'success');
            loadRegistrations(); // Reload to update UI
        } else {
            showToast('更新失敗', '無法更新繳費狀態', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('連線錯誤', '伺服器連線錯誤', 'error');
    }
}

function exportDataExcel() {
    try {
        if (typeof XLSX === 'undefined') {
            showToast('元件載入中', 'Excel 元件尚未載入，請稍後或使用 CSV 匯出', 'warning');
            return;
        }

        // Prepare data for Excel
        const headers = ['ID', '學生姓名', '生日', '班級', '課程數', '用品數', '繳費', '報名時間', '更新時間'];
        const data = allRegistrations.map(reg => ({
            'ID': reg.id,
            '學生姓名': reg.student_name,
            '生日': reg.birthday || '',
            '班級': reg.class_name || '未指定',
            '課程數': reg.course_count,
            '用品數': reg.supply_count,
            '繳費': reg.is_paid ? '已繳費' : '未繳費',
            '報名時間': formatDate(reg.created_at),
            '更新時間': formatDate(reg.updated_at)
        }));

        // Create worksheet
        const ws = XLSX.utils.json_to_sheet(data, { header: headers });

        // Adjust column widths
        const wscols = [
            { wch: 10 }, // ID
            { wch: 15 }, // Name
            { wch: 12 }, // Birthday
            { wch: 15 }, // Class
            { wch: 10 }, // Courses
            { wch: 10 }, // Supplies
            { wch: 20 }, // Created At
            { wch: 20 }  // Updated At
        ];
        ws['!cols'] = wscols;

        // Create workbook
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, "報名資料");

        // Generate filename
        const filename = `報名資料_${new Date().toISOString().split('T')[0]}.xlsx`;

        // Export using manual Blob method for better compatibility
        const wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
        const blob = new Blob([wbout], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });

        // Create download link
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();

        // Cleanup
        setTimeout(() => {
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        }, 0);

        showToast('匯出成功', '報名資料已匯出為 Excel 檔案', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('匯出失敗', '無法產生 Excel 檔案', 'error');
    }
}

function exportDataCSV() {
    // Convert to CSV
    const headers = ['ID', '學生姓名', '生日', '班級', '課程數', '用品數', '繳費', '報名時間', '更新時間'];
    const rows = allRegistrations.map(reg => [
        reg.id,
        reg.student_name,
        reg.birthday || '',
        reg.class_name || '未指定',
        reg.course_count,
        reg.supply_count,
        reg.is_paid ? '已繳費' : '未繳費',
        formatDate(reg.created_at),
        formatDate(reg.updated_at)
    ]);

    // Add BOM for Excel Chinese compatibility
    let csv = '\uFEFF' + headers.join(',') + '\n';
    csv += rows.map(row => row.map(field => `"${field}"`).join(',')).join('\n');

    // Download
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `報名資料_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast('匯出成功', '報名資料已匯出為 CSV 檔案', 'success');
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('zh-TW', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function showError(message) {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = `
        <tr>
            <td colspan="8" class="empty-state">
                <div class="empty-state-icon">❌</div>
                <div>${message}</div>
            </td>
        </tr>
    `;
}

// Confirmation helper
let currentConfirmCallback = null;

function showConfirm(title, message, callback) {
    document.getElementById('confirmTitle').textContent = title;
    document.getElementById('confirmMessage').innerText = message;
    currentConfirmCallback = callback;

    const modal = document.getElementById('confirmModal');
    const confirmBtn = document.getElementById('confirmBtn');

    // Remove old listeners to avoid duplicates
    const newBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);

    newBtn.addEventListener('click', () => {
        if (currentConfirmCallback) currentConfirmCallback();
        closeConfirmModal();
    });

    modal.style.display = 'block';
}

function closeConfirmModal() {
    document.getElementById('confirmModal').style.display = 'none';
    currentConfirmCallback = null;
}

// Close modal when clicking outside
window.onclick = function (event) {
    const detailModal = document.getElementById('detailModal');
    const courseModal = document.getElementById('courseModal');
    const confirmModal = document.getElementById('confirmModal');
    if (event.target === detailModal) {
        closeModal();
    }
    if (event.target === courseModal) {
        closeCourseModal();
    }
    if (event.target === confirmModal) {
        closeConfirmModal();
    }
}
