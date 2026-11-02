(function () {
    const CPVTS = {};

    function $(id) {
        return document.getElementById(id);
    }

    function setTheme(theme) {
        const isDark = theme === "dark";
        document.body.classList.toggle("dark", isDark);
        localStorage.setItem("cpvts-theme", theme);

        const label = $("themeLabel");
        const badge = $("themeBadge");
        const icon = $("themeIcon");

        if (label) {
            label.textContent = isDark ? "Light Mode" : "Dark Mode";
        }
        if (badge) {
            badge.textContent = isDark ? "Dark" : "Light";
        }
        if (icon) {
            if (isDark) {
                // Sun icon for switching back to light mode
                icon.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
            } else {
                // Moon icon for switching to dark mode
                icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
            }
        }
    }

    function initTheme() {
        const saved = localStorage.getItem("cpvts-theme") || "light";
        setTheme(saved);
        const btn = $("themeToggle");
        if (btn) {
            btn.addEventListener("click", function () {
                const next = document.body.classList.contains("dark") ? "light" : "dark";
                setTheme(next);
            });
        }
    }

    function initSidebar() {
        const sidebar = $("sidebar");
        const btn = $("menuBtn");
        const backdrop = $("sidebarBackdrop");
        if (!sidebar || !btn) return;

        function close() {
            sidebar.classList.remove("open");
            if (backdrop) backdrop.classList.remove("show");
        }

        btn.addEventListener("click", function () {
            const isOpen = sidebar.classList.toggle("open");
            if (backdrop) backdrop.classList.toggle("show", isOpen);
        });

        if (backdrop) backdrop.addEventListener("click", close);

        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && sidebar.classList.contains("open")) {
                close();
            }
        });
    }

    function hourValid(value) {
        if (value === "" || value === null || value === undefined) return false;
        if (!/^-?\d+$/.test(String(value).trim())) return false;
        const n = Number(value);
        return n >= 0 && n <= 23;
    }

    function showClientError(form, message) {
        let box = form.querySelector(".client-error");
        if (!box) {
            box = document.createElement("div");
            box.className = "flash error client-error";
            form.prepend(box);
        }
        box.innerHTML =
            '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">' +
            '<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>' +
            '<span>' + escapeHtml(message) + '</span>';
    }

    function initEntryForm() {
        const form = $("entryForm");
        if (!form) return;
        form.addEventListener("submit", function (event) {
            const number = (form.vehicle_number.value || "").trim();
            const type = form.vehicle_type.value;
            const category = form.owner_category.value;
            const hour = form.entry_time.value;
            if (!number) {
                event.preventDefault();
                showClientError(form, "Vehicle number cannot be empty.");
                return;
            }
            if (!type) {
                event.preventDefault();
                showClientError(form, "Vehicle type must be selected.");
                return;
            }
            if (!category) {
                event.preventDefault();
                showClientError(form, "Owner category must be selected.");
                return;
            }
            if (!hourValid(hour)) {
                event.preventDefault();
                showClientError(form, "Entry time must be between 0 and 23.");
            }
        });
    }

    function initExitForm() {
        const form = $("exitForm");
        if (!form) return;
        form.addEventListener("submit", function (event) {
            const identifier = (form.identifier.value || "").trim();
            const hour = form.exit_time.value;
            if (!identifier) {
                event.preventDefault();
                showClientError(form, "Enter a vehicle number or spot ID.");
                return;
            }
            if (!hourValid(hour)) {
                event.preventDefault();
                showClientError(form, "Exit time must be between 0 and 23.");
            }
        });
    }

    function initSearchForm() {
        const form = $("searchForm");
        if (!form) return;
        form.addEventListener("submit", function (event) {
            const number = (form.vehicle_number.value || "").trim();
            if (!number) {
                event.preventDefault();
                showClientError(form, "Vehicle number cannot be empty.");
            }
        });
    }

    function escapeHtml(text) {
        return String(text == null ? "" : text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function renderSlotCard(slot) {
        const occupied = slot.status === "Occupied";
        const reserved = slot.status === "Reserved" || (slot.is_reserved && !occupied);
        const isVipOccupied = occupied && slot.is_reserved;
        const catClass = (slot.owner_category || "").toLowerCase().replace(/[^a-z0-9]/g, "-");
        let body = "";
        let cardClass = "available";
        let headerStatus = escapeHtml(String(slot.status).toUpperCase());

        if (occupied) {
            cardClass = "occupied";
            if (isVipOccupied) {
                headerStatus = "OCCUPIED (VIP)";
            }
            body = '<p class="slot-vehicle">' + escapeHtml(slot.vehicle_number) + '</p>' +
                   '<p class="slot-time">Entry ' + escapeHtml(slot.entry_time_display) + '</p>' +
                   '<p class="slot-category"><span class="cat-chip ' + escapeHtml(catClass) + '">' + escapeHtml(slot.owner_category) + '</span>' +
                   (isVipOccupied ? '<span class="cat-chip reserved" style="margin-left: 4px;">VIP Bay</span>' : '') + '</p>';
        } else if (reserved) {
            cardClass = "reserved";
            headerStatus = "RESERVED";
            body = '<p class="slot-reserved-badge">VIP / Emergency</p>' +
                   '<p class="slot-time">Reserved by Security</p>' +
                   '<p class="slot-category"><span class="cat-chip reserved">Official VIP</span></p>';
        } else {
            body = '<p class="muted">Ready for assignment</p>';
        }
        return (
            '<article class="slot-card ' + cardClass + '">' +
            '<header><strong>' + escapeHtml(slot.slot_id) + '</strong><span>' +
            headerStatus + '</span></header>' + body + '</article>'
        );
    }

    function renderZones(data) {
        const two = (data.two_wheeler_zone || []).map(renderSlotCard).join("");
        const four = (data.four_wheeler_zone || []).map(renderSlotCard).join("");
        return (
            '<div class="zone-block">' +
            '<div class="zone-header"><div class="zone-title-wrap"><span class="zone-badge two-wheeler">Zone A</span><h2>Two-Wheeler Zone</h2></div><span class="zone-capacity-pill">10 Bays (T-01 to T-10)</span></div>' +
            '<div class="slot-grid">' + two + '</div></div>' +
            '<div class="zone-block">' +
            '<div class="zone-header"><div class="zone-title-wrap"><span class="zone-badge four-wheeler">Zone B</span><h2>Four-Wheeler Zone</h2></div><span class="zone-capacity-pill">5 Bays (F-01 to F-05)</span></div>' +
            '<div class="slot-grid">' + four + '</div></div>'
        );
    }

    function renderRecent(rows) {
        if (!rows || !rows.length) {
            return '<tr class="empty-row"><td colspan="8">No parking activity yet. Check in the first vehicle to begin.</td></tr>';
        }
        return rows.map(function (txn) {
            const catClass = (txn.owner_category || "").toLowerCase().replace(/[^a-z0-9]/g, "-");
            return (
                '<tr>' +
                '<td class="vehicle-col">' + escapeHtml(txn.vehicle_number) + '</td>' +
                '<td><span class="slot-tag">' + escapeHtml(txn.slot_id) + '</span></td>' +
                '<td>' + escapeHtml(txn.vehicle_type) + '</td>' +
                '<td><span class="cat-pill ' + escapeHtml(catClass) + '">' + escapeHtml(txn.owner_category) + '</span></td>' +
                '<td>' + escapeHtml(txn.entry_time_display) + '</td>' +
                '<td>' + escapeHtml(txn.exit_time_display) + '</td>' +
                '<td class="fee-col">' + escapeHtml(txn.fee_display) + '</td>' +
                '<td><span class="status-chip ' + escapeHtml(String(txn.status).toLowerCase()) + '">' +
                escapeHtml(txn.status) + '</span></td>' +
                '</tr>'
            );
        }).join("");
    }

    CPVTS.startDashboardRefresh = function () {
        const stats = $("statsGrid");
        if (!stats) return;
        async function refresh() {
            try {
                const response = await fetch("/api/dashboard");
                if (!response.ok) return;
                const data = await response.json();
                if ($("statTotal")) $("statTotal").textContent = data.total_slots;
                if ($("statTwo")) $("statTwo").textContent = data.two_wheeler_slots;
                if ($("statFour")) $("statFour").textContent = data.four_wheeler_slots;
                if ($("statOccupied")) $("statOccupied").textContent = data.occupied_slots;
                if ($("statAvailable")) $("statAvailable").textContent = data.available_slots;
                if ($("statTwoAvail")) $("statTwoAvail").textContent = data.two_wheeler_available;
                if ($("statFourAvail")) $("statFourAvail").textContent = data.four_wheeler_available;
                if ($("statToday")) $("statToday").textContent = data.vehicles_today;
                if ($("statFees")) $("statFees").textContent = "₹" + data.fees_collected;
                const pill = $("occupancyPill");
                if (pill) pill.textContent = data.occupancy_percent + "% occupied";
                const bar = $("occupancyBar");
                if (bar) bar.style.width = data.occupancy_percent + "%";
                const zones = $("zoneBoards");
                if (zones) zones.innerHTML = renderZones(data);
                const table = document.querySelector("#recentTable tbody");
                if (table) table.innerHTML = renderRecent(data.recent_transactions);

                // Live synchronization with 3D Parking Lot Visualizer
                if (window.Parking3D && window.Parking3D.initialized) {
                    window.Parking3D.update(data);
                }
            } catch (err) {
                /* Keep last known dashboard values if the API is briefly unavailable. */
            }
        }
        refresh();
        setInterval(refresh, 4000);
    };

    document.addEventListener("DOMContentLoaded", function () {
        initTheme();
        initSidebar();
        initEntryForm();
        initExitForm();
        initSearchForm();

        // Initialize 3D Parking Lot Visualizer if container exists
        if (window.Parking3D && $("parking3dContainer")) {
            window.Parking3D.init("parking3dContainer");
        }
    });

    window.CPVTS = CPVTS;
})();
