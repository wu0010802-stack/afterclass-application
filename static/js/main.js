
// Registration time settings (fetched from server)
let REGISTRATION_START_DATE = null;
let REGISTRATION_END_DATE = null;
let courseVideos = {};

// Fetch registration time settings from server
async function fetchRegistrationTime() {
    try {
        const response = await apiFetch('/api/settings/registration-time');

        if (response.ok) {
            const data = await response.json();
            if (data.start) {
                REGISTRATION_START_DATE = new Date(data.start);
            }
            if (data.end) {
                REGISTRATION_END_DATE = new Date(data.end);
            }
            checkRegistrationTime();
        }
    } catch (error) {
        console.error('Failed to fetch registration time:', error);
        // Use defaults if API fails
        REGISTRATION_START_DATE = new Date('2026-02-02T16:00:00');
        REGISTRATION_END_DATE = new Date('2026-02-20T23:59:00');
        checkRegistrationTime();
    }
}

function checkRegistrationTime() {
    const now = new Date();
    const notice = document.getElementById('registrationNotice');
    const daysRemainingEl = document.getElementById('daysRemaining');

    if (!REGISTRATION_START_DATE || !REGISTRATION_END_DATE) {
        if (notice) notice.style.display = 'none';
        return;
    }

    if (now < REGISTRATION_START_DATE) {
        const daysLeft = Math.ceil((REGISTRATION_START_DATE - now) / (1000 * 60 * 60 *
            24));
        if (daysRemainingEl) daysRemainingEl.textContent = daysLeft;
        if (notice) {
            notice.style.display = 'block';
            notice.querySelector('strong').textContent = '報名尚未開放';
        }
    } else if (now > REGISTRATION_END_DATE) {
        if (notice) {
            notice.style.display = 'block';
            notice.style.background = 'linear-gradient(135deg, #f8d7da, #f5c6cb)';
            notice.style.borderLeftColor = '#dc3545';
            notice.innerHTML = `
    <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 24px;">🔒</span>
        <div>
            <strong style="color: #721c24;">報名已截止</strong><br>
            <span style="font-size: 14px; color: #721c24;">感謝您的關注，本期報名已結束</span>
        </div>
    </div>
    `;
        }
    } else {
        if (notice) notice.style.display = 'none';
    }
}

// Check remaining course availability
async function fetchCourseAvailability() {
    try {
        const response = await apiFetch('/api/courses/availability');

        if (response.ok) {
            const availability = await response.json();
            updateCourseAvailabilityUI(availability);
        }
    } catch (error) {
        console.error('Failed to fetch availability:', error);
    }
}

function updateCourseAvailabilityUI(availability) {
    document.querySelectorAll('#courseList input[type="checkbox"]').forEach(checkbox => {
        const courseName = checkbox.value;
        if (availability[courseName] !== undefined) {
            const remaining = availability[courseName];
            const label = checkbox.closest('label');
            const remCountSpan = label.querySelector('.rem-count');

            if (remCountSpan) {
                // Check if we already added it (to avoid duplicates if called multiple times)
                let qtySpan = label.querySelector('.qty-display');
                if (!qtySpan) {
                    qtySpan = document.createElement('span');
                    qtySpan.className = 'qty-display';
                    qtySpan.style.color = '#d93025';
                    qtySpan.style.fontWeight = 'bold';
                    qtySpan.style.marginLeft = '8px';
                    // Insert content after rem-count
                    remCountSpan.parentNode.insertBefore(qtySpan, remCountSpan.nextSibling);
                }

                qtySpan.textContent = `(剩餘: ${remaining})`;

                // Optional: Disable if 0
                if (remaining <= 0) {
                    checkbox.disabled = true;
                    label.style.opacity = '0.6';
                    qtySpan.textContent = `(已額滿 Full)`;
                }
            }
        }
    });
}

// Submit button for new registrations
document.addEventListener('DOMContentLoaded', () => {
    const submitBtn = document.getElementById('submitBtn');
    if (submitBtn) {
        submitBtn.addEventListener('click', async function () {
            // Check registration time
            const now = new Date();

            if (REGISTRATION_START_DATE && now < REGISTRATION_START_DATE) {
                const daysLeft = Math.ceil((REGISTRATION_START_DATE - now) / (1000 * 60 * 60 * 24));
                const startStr = REGISTRATION_START_DATE.toLocaleString('zh-TW');
                showToast(`報名尚未開放\n報名開始時間：${startStr}\n距離開放還有 ${daysLeft} 天`, 'warning', 8000);
                return;
            }

            if (REGISTRATION_END_DATE && now > REGISTRATION_END_DATE) {
                showToast('報名已截止\n感謝您的關注，本期報名已結束', 'error', 8000);
                return;
            }

            const name = document.getElementById('studentName').value;
            const birthday = document.getElementById('studentBirthday').value;
            const classSelected = document.querySelector('input[name="class"]:checked');

            const selectedCourses = [];
            document.querySelectorAll('#courseList input[type="checkbox"]:checked').forEach(cb => {
                selectedCourses.push({
                    name: cb.value,
                    price: cb.dataset.price
                });
            });

            const selectedSupplies = [];
            document.querySelectorAll('#suppliesList input[type="checkbox"]:checked').forEach(cb => {
                selectedSupplies.push({
                    name: cb.value,
                    price: cb.dataset.price
                });
            });

            if (!name) {
                showToast('請輸入幼兒姓名\nPlease enter student name.', 'error');
                return;
            }

            if (!birthday) {
                showToast('請輸入幼兒生日\nPlease enter birthday.', 'error');
                return;
            }

            const payload = {
                name: name,
                birthday: birthday,
                class: classSelected ? classSelected.value : 'Unspecified',
                courses: selectedCourses,
                supplies: selectedSupplies,
                totalItems: selectedCourses.length + selectedSupplies.length
            };

            try {
                const response = await apiFetch('/submit-registration', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    const result = await response.json();
                    showToast('報名成功！\nRegistration Successful!', 'success');
                    document.querySelector('form').reset();
                    // Reload availability
                    fetchCourseAvailability();
                } else {
                    const error = await response.json();
                    showToast(error.message || '報名失敗，請稍後再試。\nRegistration failed.', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('伺服器連線錯誤。\nServer connection error.', 'error');
            }
        });
    }

    // Initialize video loading
    loadCourseVideos();
    fetchRegistrationTime();
    fetchCourseAvailability();
});

// Video Modal Logic
async function loadCourseVideos() {
    try {
        const response = await apiFetch('/api/course-videos');
        if (response.ok) {
            courseVideos = await response.json();
            renderVideoButtons();
        }
    } catch (error) {
        console.error('Failed to load course videos:', error);
    }
}

function renderVideoButtons() {
    document.querySelectorAll('#courseList .course-item').forEach(item => {
        const checkbox = item.querySelector('input[type="checkbox"]');
        const courseName = checkbox.value;
        const videoUrl = courseVideos[courseName];

        // Remove existing button if any
        const existingBtn = item.querySelector('.video-btn');
        if (existingBtn) existingBtn.remove();

        if (videoUrl) {
            const btn = document.createElement('button');
            btn.className = 'video-btn';
            btn.type = 'button'; // Prevent form submission
            btn.innerHTML = '▶ 課程介紹';
            btn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                openVideoModal(courseName, videoUrl);
            };

            // Append to course text
            const courseText = item.querySelector('.course-text');
            courseText.appendChild(btn);
        }
    });
}

function openVideoModal(title, url) {
    const modal = document.getElementById('videoModal');
    const videoContainer = document.getElementById('videoContainer');
    const titleEl = document.getElementById('videoModalTitle');

    titleEl.textContent = title;
    modal.classList.add('active');

    // Clear previous content
    videoContainer.innerHTML = '';

    // Check if YouTube
    let youtubeId = null;
    if (url.includes('youtube.com/watch?v=')) {
        youtubeId = url.split('v=')[1].split('&')[0];
    } else if (url.includes('youtu.be/')) {
        youtubeId = url.split('youtu.be/')[1].split('?')[0];
    } else if (url.includes('youtube.com/embed/')) {
        youtubeId = url.split('embed/')[1].split('?')[0];
    }

    if (youtubeId) {
        // Render YouTube Iframe
        const iframe = document.createElement('iframe');
        iframe.width = '100%';
        iframe.height = '450'; // Adjust as needed
        iframe.src = `https://www.youtube.com/embed/${youtubeId}?autoplay=1`;
        iframe.frameBorder = '0';
        iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
        iframe.allowFullscreen = true;
        iframe.style.border = 'none';
        iframe.style.borderRadius = '8px';
        iframe.id = 'videoIframe'; // Tracking ID
        videoContainer.appendChild(iframe);
    } else {
        // Render Standard Video
        const video = document.createElement('video');
        video.id = 'videoPlayer';
        video.controls = true;
        video.autoplay = true;
        video.style.width = '100%';
        video.style.borderRadius = '8px';
        video.src = url;

        // Add default error message
        video.innerHTML = '您的瀏覽器不支援影片播放';

        videoContainer.appendChild(video);

        try {
            video.play();
        } catch (e) {
            console.log('Auto-play blocked:', e);
        }
    }
}

function closeVideoModal() {
    const modal = document.getElementById('videoModal');
    const videoContainer = document.getElementById('videoContainer');

    // Clear content to stop playing
    if (videoContainer) {
        videoContainer.innerHTML = '';
    }
    modal.classList.remove('active');
}

// Close modal when clicking outside
const videoModal = document.getElementById('videoModal');
if (videoModal) {
    videoModal.addEventListener('click', function (e) {
        if (e.target === this) {
            closeVideoModal();
        }
    });
}
