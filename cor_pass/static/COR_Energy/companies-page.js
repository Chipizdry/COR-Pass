/* Глобальні змінні */
let companyList = [];
let filteredCompanyList = [];
let activeCompany = null; // поточний вибраний клієнт (для модалок / контекстного меню)

const STATUS_COLORS = {
   pending: "#0B90C9",
   active: "#49AC26",
   blocked: "#DF1125",
   rejected: "#000", // Заявку відхилено - поки без кольору
   limit_exceeded: "#FD7441"
};

// DOM-посилання
const tbody = document.getElementById("tableBody");
const footerInfo = document.getElementById("footerInfo");
const searchInput = document.getElementById("searchInput");
const contextMenu = document.getElementById("actionsMenu");

// Модалки
const infoModal = document.getElementById("infoModal");
const limitModal = document.getElementById("limitModal");
const blockModal = document.getElementById("blockModal");
const deleteModal = document.getElementById("deleteModal");

//Переклад
let lang = "uk";

if (typeof getSavedLang === "function") {
   lang = getSavedLang();
}

const dict = (typeof translations !== "undefined" && translations?.[lang]) || {};

/* Бекдроп прив'язаний до класу .active у модалок */
function openModal(modal) {
   if (!modal) return;
   modal.classList.add("active");
}

function closeModal(modal) {
   if (!modal) return;
   modal.classList.remove("active");
}

function closeAllModals() {
   document.querySelectorAll(".modal.active").forEach(m => m.classList.remove("active"));
}

// Всі кнопки та хрестики, які закривають свою модалку
function initGenericCloseButtons() {
   // Кнопки "Відмінити"
   document.querySelectorAll(".modal .cancelBtn").forEach(btn => {
      btn.addEventListener("click", () => {
         const modal = btn.closest(".modal");
         closeModal(modal);
      });
   });

   // Хрестики
   document.querySelectorAll(".modal .modal-button.close").forEach(btn => {
      btn.addEventListener("click", () => {
         const modal = btn.closest(".modal");
         closeModal(modal);
      });
   });
}

/* Завантаження компаній з беку */

async function getCompanies() {
   if (!checkToken()) return;

   try {
      const params = new URLSearchParams();
      params.set("limit", "100");

      const res = await fetch(`${API_BASE_URL}/api/admin/corporate-clients?${params.toString()}`, {
         method: "GET",
         headers: {
            "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
            "Content-Type": "application/json",
            "Accept": "application/json"
         }
      });

      if (!res.ok) {
         console.error("Помилка при отриманні корпоративних клієнтів", res.status);
         return;
      }

      const data = await res.json();
      const items = Array.isArray(data) ? data : [];

      companyList = items.map(item => ({
         id: item.id,
         company_form: item.company_format,
         full_company_name: item.company_name,
         company_address: item.address,
         phone: item.phone_number,
         email: item.email,
         edrpou: item.tax_id,
         balance: item.current_balance,
         status: item.status,    // pending / active / blocked / rejected / limit_exceeded
         // додатково для модалок:
         owner_cor_id: item.owner_cor_id,
         fuel_limit: item.fuel_limit,
         rejection_reason: item.rejection_reason,
      }));

      filteredCompanyList = [...companyList];
      renderTableData(filteredCompanyList);

   } catch (err) {
      console.error("Помилка мережі при завантаженні компаній", err);
   }
}
/* Рендер таблиці */

function renderTableData(list) {
   tbody.innerHTML = "";

   list.forEach(company => {
      const statusKey = company.status;
      const color = STATUS_COLORS[statusKey];

      const tr = document.createElement("tr");
      tr.dataset.id = company.id ?? "";
      tr.dataset.status = statusKey || "";

      tr.innerHTML = `
        <td>${company.company_form || ""}</td>
        <td>${company.full_company_name || ""}</td>
        <td>${company.company_address || ""}</td>
        <td>${company.phone || ""}</td>
        <td>${company.email || ""}</td>
        <td>${company.edrpou || ""}</td>
        <td>${company.balance != null ? company.balance : ""}</td>
        <td>
          <span class="status">
            <span class="status-container">
              <span class="status-dot" style="background:${color}"></span>
              <span class="status-label"
                     data-translate="status_${statusKey}">
                     ${dict[`status_${statusKey}`] || statusKey}
               </span>

              <button class="status-menu-btn"
                      type="button"
                      aria-label="${dict.statusMenuLabel || 'Дії з користувачем'}">
                <!-- контекстне меню на три крапки -->
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
                     xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M10 18.375C10 17.3395 10.8395 16.5 11.875 16.5C12.9105 16.5 13.75 17.3395 13.75 18.375C13.75 19.4105 12.9105 20.25 11.875 20.25C10.8395 20.25 10 19.4105 10 18.375Z"
                    fill="#B1A1DA" />
                  <path
                    d="M10 12.125C10 11.0895 10.8395 10.25 11.875 10.25C12.9105 10.25 13.75 11.0895 13.75 12.125C13.75 13.1605 12.9105 14 11.875 14C10.8395 14 10 13.1605 10 12.125Z"
                    fill="#B1A1DA" />
                  <path
                    d="M10 5.875C10 4.83947 10.8395 4 11.875 4C12.9105 4 13.75 4.83947 13.75 5.875C13.75 6.91053 12.9105 7.75 11.875 7.75C10.8395 7.75 10 6.91053 10 5.875Z"
                    fill="#B1A1DA" />
                </svg>
              </button>
            </span>
          </span>
        </td>
      `;

      // Інформація про клієнта
      tr.addEventListener("click", () => {
         activeCompany = company;
         openCompanyInfoModal(company);
      });

      // Клік по трьох крапках не має відкривати її!
      const menuBtn = tr.querySelector(".status-menu-btn");
      if (menuBtn) {
         menuBtn.addEventListener("click", (evt) => {
            evt.stopPropagation();
            activeCompany = company;
            openContextMenu(menuBtn, company);
         });
      }

      tbody.appendChild(tr);
   });

   footerInfo.textContent = `${dict.totalUsers || "Всього користувачів"}: ${list.length}`;
}

/* Пошук */
function initSearch() {
   if (!searchInput) return;
   searchInput.addEventListener("input", e => {
      const q = e.target.value.toLowerCase().trim();
      if (!q) {
         filteredCompanyList = [...companyList];
      } else {
         filteredCompanyList = companyList.filter(row =>
            Object.values(row).some(val =>
               val != null && val.toString().toLowerCase().includes(q)
            )
         );
      }
      // sortAndRender(currentSort.field, currentSort.dir);
   });
}

/* Контекстне меню для рядка */
function openContextMenu(anchorEl, company) {
   if (!contextMenu) return;

   const rect = anchorEl.getBoundingClientRect();
   contextMenu.style.top = `${rect.bottom + window.scrollY}px`;
   contextMenu.style.left = `${rect.right + window.scrollX - contextMenu.offsetWidth}px`;
   contextMenu.classList.add("visible");

   contextMenu.dataset.id = company.id ?? "";

   // Клік поза меню - закриває його
   function outsideClickHandler(e) {
      if (!contextMenu.contains(e.target) && e.target !== anchorEl) {
         closeContextMenu();
         document.removeEventListener("click", outsideClickHandler);
      }
   }
   document.addEventListener("click", outsideClickHandler);
}

function closeContextMenu() {
   if (!contextMenu) return;
   contextMenu.classList.remove("visible");
}

function initContextMenuActions() {
   if (!contextMenu) return;

   const limitBtn = contextMenu.querySelector("#limit");
   const blockBtn = contextMenu.querySelector("#block_company");
   const deleteBtn = contextMenu.querySelector("#delete_company");

   limitBtn?.addEventListener("click", () => {
      closeContextMenu();
      if (!activeCompany) return;
      openLimitModal(activeCompany);
   });

   blockBtn?.addEventListener("click", () => {
      closeContextMenu();
      if (!activeCompany) return;
      openModal(blockModal);
   });

   deleteBtn?.addEventListener("click", () => {
      closeContextMenu();
      if (!activeCompany) return;
      openModal(deleteModal);
   });
}

/* Модалка Інформація про користувача */
function fillInfoModalFields(company) {
   if (!infoModal) return;
   infoModal.querySelectorAll(".info-field").forEach(field => {
      const labelEl = field.querySelector("[data-field]");
      if (!labelEl) return;
      const key = labelEl.dataset.field;
      const valueEl = labelEl.nextElementSibling;
      if (valueEl) {
         valueEl.textContent = company[key] || "";
      }
   });
}

function openCompanyInfoModal(company) {
   activeCompany = company;
   fillInfoModalFields(company);
   openModal(infoModal);
}

function initInfoModalActions() {
   if (!infoModal) return;

   const submitBtn = infoModal.querySelector(".submitBtn");
   const rejectBtn = infoModal.querySelector(".rejectBtn");
   // submitBtn = статус з pending > active
   submitBtn?.addEventListener("click", async () => {
      if (!activeCompany) return;

      const reqId = activeCompany.id;
      if (!reqId) {
         closeModal(infoModal);
         return;
      }

      if (!checkToken()) return;

      try {
         const res = await fetch(`${API_BASE_URL}/api/admin/corporate-requests/${reqId}/approve`, {
            method: "POST",
            headers: {
               "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
               "Content-Type": "application/json",
               "Accept": "application/json"
            }
         });

         if (!res.ok) {
            console.error("Помилка підтвердження заявки", res.status);
         } else {
            getCompanies()
         }
      } catch (err) {
         console.error("Помилка мережі при підтвердженні заявки", err);
      } finally {
         closeModal(infoModal);
      }
   });

   // rejectBtn = статус з pending > reject
   rejectBtn?.addEventListener("click", async () => {
      if (!activeCompany) return;

      const reqId = activeCompany.id;
      if (!reqId) {
         closeModal(infoModal);
         return;
      }

      if (!checkToken()) return;

      try {
         const res = await fetch(`${API_BASE_URL}/api/admin/corporate-requests/${reqId}/reject`, {
            method: "POST",
            headers: {
               "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
               "Content-Type": "application/json",
               "Accept": "application/json"
            },
            body: JSON.stringify({
               reason: "" // якщо додаси інпут для причини – підставиш його сюди
            })
         });

         if (!res.ok) {
            console.error("Помилка відхилення заявки", res.status);
         } else {
            getCompanies()
         }
      } catch (err) {
         console.error("Помилка мережі при відхиленні заявки", err);
      } finally {
         closeModal(infoModal);
      }
   });
}
/* Модалка Ліміти */

function openLimitModal(company) {
   if (!limitModal) return;
   activeCompany = company;

   const nameEl = limitModal.querySelector(".company_name");
   if (nameEl) {
      nameEl.textContent = company.full_company_name || "";
   }

   const amountInput = limitModal.querySelector('input[type="number"]');
   if (amountInput) amountInput.value = "";

   toggleLimitButtonsEnabled(false);

   openModal(limitModal);
}

function toggleLimitButtonsEnabled(enabled) {
   const resetBtn = limitModal?.querySelector(".resetLimitBtn");
   const applyBtn = limitModal?.querySelector(".applyBtn");
   [resetBtn, applyBtn].forEach(btn => {
      if (!btn) return;
      btn.classList.toggle("enable", enabled);
   });
}

function initLimitModalActions() {
   if (!limitModal) return;

   const amountInput = limitModal.querySelector('input[type="number"]');
   const resetBtn = limitModal.querySelector(".resetLimitBtn");
   const applyBtn = limitModal.querySelector(".applyBtn");

   // Кнопки активні/не активні при заповненні суми
   amountInput?.addEventListener("input", () => {
      const val = amountInput.value.trim();
      const enabled = val !== "";
      console.log(enabled, "enabled")
      toggleLimitButtonsEnabled(enabled);
   });

   resetBtn?.addEventListener("click", async () => {
      if (!resetBtn.classList.contains("enable")) return;

      if (!activeCompany || !checkToken()) {
         closeModal(limitModal);
         return;
      }
   });

   // Кнопка "Застосувати" - відправляє оновлені дані PUT /limits
   applyBtn?.addEventListener("click", async () => {
      if (!applyBtn.classList.contains("enable")) return;

      if (!activeCompany || !checkToken()) {
         closeModal(limitModal);
         return;
      }

      const amountInput = limitModal.querySelector('input[type="number"]');
      const amount = amountInput ? Number(amountInput.value.replace(",", ".")) : null;

      try {
         const res = await fetch(`${API_BASE_URL}/api/admin/corporate-clients/${activeCompany.id}/limits`, {
            method: "PUT",
            headers: {
               "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
               "Content-Type": "application/json",
               "Accept": "application/json"
            },
            body: JSON.stringify({
               credit_limit: amount,
               balance_level_alert_limit: amount,
               balance_level_hook_url: "https://dev-corid.cor-medical.ua/api/webhooks/balance-level-alert"
            })
         });

         if (!res.ok) {
            console.error("Помилка при оновленні ліміту", res.status);
         }
      } catch (err) {
         console.error("Помилка мережі при оновленні ліміту", err);
      } finally {
         closeModal(limitModal);
      }
   });
}

/* Алерт "Заблокувати" */
function initBlockModalActions() {
   if (!blockModal) return;
   const blockBtn = blockModal.querySelector(".blockBtn");
   const cancelBtn = blockModal.querySelector(".cancelBtn");

   cancelBtn?.addEventListener("click", () => {
      closeModal(blockModal);
   });

   blockBtn?.addEventListener("click", async () => {
      if (!activeCompany) return;

      // беку ще нема? тому поки локально
      activeCompany.status = "blocked";
      getCompanies()
      closeModal(blockModal);
   });
}

/* Алерт "Видалити компанію" */
function initDeleteModalActions() {
   if (!deleteModal) return;
   const deleteBtn = deleteModal.querySelector(".deleteBtn");
   const cancelBtn = deleteModal.querySelector(".cancelBtn");

   cancelBtn?.addEventListener("click", () => closeModal(deleteModal));

   deleteBtn?.addEventListener("click", async () => {
      if (!activeCompany || !checkToken()) return;

      try {
         const res = await fetch(`${API_BASE_URL}/api/admin/corporate-clients/${activeCompany.id}`, {
            method: "DELETE",
            headers: {
               "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
               "Accept": "application/json"
            }
         });

         if (!res.ok) {
            console.error("Помилка при видаленні компанії", res.status);
         } else {
            getCompanies()
         }
      } catch (err) {
         console.error("Помилка мережі при видаленні компанії", err);
      } finally {
         closeModal(deleteModal);
      }
   });
}

/* Ініціалізація */
document.addEventListener("DOMContentLoaded", () => {
   initGenericCloseButtons();
   initSearch();
   initContextMenuActions();
   initInfoModalActions();
   initLimitModalActions();
   initBlockModalActions();
   initDeleteModalActions();
   getCompanies();
});
