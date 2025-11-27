(() => {
  "use strict";

  const VALUE_PLACEHOLDER = "\u2014";
  const DEFAULT_LANG = "ru";
  const STEP_SELECTORS = {
    diploma: "#step4Modal",
    certificate: "#step5Modal"
  };

  const PHOTO_PLACEHOLDER =
    "data:image/svg+xml;charset=UTF-8," +
    encodeURIComponent(
      `<svg width="130" height="130" viewBox="0 0 130 130" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="130" height="130" rx="65" fill="#EFECF8"/>
        <circle cx="65" cy="54" r="26" fill="#D4C6F1"/>
        <path d="M25 112C25 90.0132 42.0132 73 64 73H66C87.9868 73 105 90.0132 105 112" stroke="#D4C6F1" stroke-width="6" stroke-linecap="round"/>
      </svg>`
    );

  const LINK_ICON = `
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M21.6944 2.18895C21.8811 2.34173 22 2.5734 22 2.8334V9.50004C22 9.72105 21.9122 9.93301 21.7559 10.0893C21.5996 10.2456 21.3877 10.3334 21.1667 10.3334C20.9457 10.3334 20.7337 10.2456 20.5774 10.0893C20.4211 9.93301 20.3333 9.72105 20.3333 9.50004V4.84506L15.0889 10.0895C15.012 10.169 14.92 10.2325 14.8183 10.2761C14.7166 10.3197 14.6073 10.3427 14.4966 10.3436C14.386 10.3445 14.2762 10.3233 14.1738 10.2814C14.0714 10.2394 13.9784 10.1775 13.9002 10.0992C13.822 10.021 13.7602 9.9279 13.7183 9.82546C13.6765 9.72303 13.6554 9.61329 13.6565 9.50264C13.6575 9.39199 13.6805 9.28266 13.7242 9.18101C13.768 9.07936 13.8315 8.98743 13.9111 8.9106L19.1539 3.66673H14.5C14.279 3.66673 14.067 3.57893 13.9107 3.42265C13.7545 3.26637 13.6667 3.05441 13.6667 2.8334C13.6667 2.61238 13.7545 2.40042 13.9107 2.24414C14.067 2.08786 14.279 2.00007 14.5 2.00007H21.1561C21.3524 1.9976 21.5427 2.06449 21.6944 2.18895ZM5.61111 3.66673C5.09541 3.66673 4.60084 3.87159 4.23618 4.23624C3.87153 4.60089 3.66667 5.09547 3.66667 5.61117V18.3889C3.66667 18.9046 3.87153 19.3992 4.23618 19.7638C4.60084 20.1285 5.09541 20.3333 5.61111 20.3333H18.3889C18.9046 20.3333 19.3992 20.1285 19.7638 19.7638C20.1285 19.3992 20.3333 18.9046 20.3333 18.3889V13.9445C20.3333 13.7235 20.4211 13.5115 20.5774 13.3552C20.7337 13.1989 20.9457 13.1111 21.1667 13.1111C21.3877 13.1111 21.5996 13.1989 21.7559 13.3552C21.9122 13.5115 22 13.7235 22 13.9445V18.3889C22 19.3466 21.6195 20.2651 20.9423 20.9423C20.2651 21.6195 19.3466 22 18.3889 22H5.61111C4.65338 22 3.73488 21.6195 3.05767 20.9423C2.38046 20.2651 2 19.3466 2 18.3889V5.61117C2 4.65344 2.38046 3.73494 3.05767 3.05773C3.73488 2.38052 4.65338 2.00007 5.61111 2.00007H10.0556C10.2766 2.00007 10.4885 2.08786 10.6448 2.24414C10.8011 2.40042 10.8889 2.61238 10.8889 2.8334C10.8889 3.05441 10.8011 3.26637 10.6448 3.42265C10.4885 3.57893 10.2766 3.66673 10.0556 3.66673H5.61111Z" fill="#7527B2"/>
    </svg>`;

  const TRANSLATIONS = window.DOCTOR_PREVIEW_I18N || {};
  const FALLBACK_LOCALE = TRANSLATIONS[DEFAULT_LANG] || {};
  const ACTIVE_LANG = resolveLanguage();
  const ACTIVE_LOCALE = TRANSLATIONS[ACTIVE_LANG] || FALLBACK_LOCALE;

  function resolveLanguage() {
    try {
      const saved = localStorage.getItem("selectedLanguage");
      if (saved && TRANSLATIONS[saved]) {
        return saved;
      }
    } catch (error) {
    }
    return DEFAULT_LANG;
  }

  function t(key) {
    return ACTIVE_LOCALE[key] ?? FALLBACK_LOCALE[key] ?? key;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatText(value) {
    const text = value ? String(value).trim() : "";
    return escapeHtml(text || VALUE_PLACEHOLDER);
  }

  function formatDate(value) {
    if (!value) return VALUE_PLACEHOLDER;
    const parts = value.split("-");
    if (parts.length === 3) {
      return `${parts[2]}.${parts[1]}.${parts[0]}`;
    }
    return escapeHtml(value);
  }

  function getInputValue(id) {
    const element = document.getElementById(id);
    return element ? element.value.trim() : "";
  }

  function getSelectLabel(id) {
    const select = document.getElementById(id);
    if (!select) return "";
    const option =
      (select.selectedOptions && select.selectedOptions[0]) ||
      select.options[select.selectedIndex];
    if (!option) return select.value.trim();
    return select.value ? option.text.trim() : "";
  }

  function getStepValue(stepSelector, inputSelector) {
    const stepRoot = document.querySelector(stepSelector);
    if (!stepRoot) return "";
    const input = stepRoot.querySelector(inputSelector);
    return input ? input.value.trim() : "";
  }

  function collectFilePreview({ inputId, labelId }, objectUrls) {
    const input = document.getElementById(inputId);
    const label = labelId ? document.getElementById(labelId) : null;
    const fallback = label ? label.textContent.trim() : t("fileNotSelected");

    if (input && input.files && input.files[0]) {
      const file = input.files[0];
      const url = URL.createObjectURL(file);
      objectUrls.push(url);
      return { name: file.name, url };
    }

    return { name: fallback || t("fileNotSelected"), url: "" };
  }

  function collectPhotoSrc(objectUrls) {
    const previewImage = document.getElementById("previewImage");
    if (
      previewImage &&
      previewImage.style.display !== "none" &&
      previewImage.src &&
      !previewImage.src.endsWith("#")
    ) {
      return previewImage.src;
    }

    const input = document.getElementById("fileInput");
    if (input && input.files && input.files[0]) {
      const url = URL.createObjectURL(input.files[0]);
      objectUrls.push(url);
      return url;
    }

    return PHOTO_PLACEHOLDER;
  }

  function buildPhotoAlt(fullName) {
    if (!fullName) return t("photoAltDefault");
    return (t("photoAltNamed") || t("photoAltDefault")).replace("{name}", fullName);
  }

  function collectPreviewData(objectUrls) {
    const profileNames = {
      lastName: getInputValue("lastName"),
      firstName: getInputValue("firstName"),
      middleName: getInputValue("middleName")
    };

    const fullName = [profileNames.firstName, profileNames.middleName, profileNames.lastName]
      .filter(Boolean)
      .join(" ")
      .trim();

    return {
      profile: {
        ...profileNames,
        birthYear: getInputValue("birthYear"),
        gender: getInputValue("gender"),
        phone: getInputValue("Phone_number"),
        email: getInputValue("workEmail"),
        photoSrc: collectPhotoSrc(objectUrls),
        photoAlt: buildPhotoAlt(fullName)
      },
      personalDocs: {
        passport: getInputValue("Passport_serial_number"),
        taxId: getInputValue("Tax_Number"),
        address: getInputValue("Addres"),
        militaryDoc: collectFilePreview(
          { inputId: "military_document", labelId: "fileName" },
          objectUrls
        )
      },
      workplace: {
        clinic: getInputValue("Clinick_Name"),
        department: getInputValue("Department"),
        jobTitle: getInputValue("Job_title"),
        specialization: getSelectLabel("specialization"),
        degree: getSelectLabel("degree"),
        attestationDate: getInputValue("birthdate")
      },
      diploma: {
        file: collectFilePreview(
          { inputId: "diploma_file", labelId: "diplomaFileName" },
          objectUrls
        ),
        date: getStepValue(STEP_SELECTORS.diploma, 'input[name="date_id"]'),
        series: getStepValue(STEP_SELECTORS.diploma, 'input[name="Serial_number"]'),
        number: getStepValue(STEP_SELECTORS.diploma, 'input[name="Number"]'),
        university: getStepValue(STEP_SELECTORS.diploma, 'input[name="University"]')
      },
      certificate: {
        file: collectFilePreview(
          { inputId: "certificateFile", labelId: "certificateFileName" },
          objectUrls
        ),
        date: getStepValue(STEP_SELECTORS.certificate, 'input[name="date_id"]'),
        series: getStepValue(STEP_SELECTORS.certificate, 'input[name="Serial_number"]'),
        number: getStepValue(STEP_SELECTORS.certificate, 'input[name="Number"]'),
        university: getStepValue(STEP_SELECTORS.certificate, 'input[name="University"]')
      }
    };
  }

  const Template = {
    logo() {
      return `
        <div class="page__logo">
          <div class="logo" aria-label="${escapeHtml(t("logoAria"))}">
            ${buildLogoSvg()}
          </div>
        </div>`;
    },

    field(label, value) {
      return `
        <div class="field">
          <span class="field__label">${escapeHtml(label)}</span>
          <span class="field__value">${value}</span>
        </div>`;
    },

    stackedField(label, value) {
      return `
        <div class="field field--stacked">
          <span class="field__label">${escapeHtml(label)}</span>
          <span class="field__value">${value}</span>
        </div>`;
    },

    fileField(label, file, ariaLabel) {
      const hasFile = Boolean(file.url);
      const linkClasses = hasFile ? "field__link" : "field__link field__link--disabled";
      const linkAttributes = hasFile
        ? `href="${escapeHtml(file.url)}" target="_blank" rel="noopener noreferrer"`
        : `href="#" aria-disabled="true" tabindex="-1"`;

      return `
        <div class="field field--stacked">
          <span class="field__label">${escapeHtml(label)}</span>
          <span class="field__value field__value--link">
            <span class="field__link-text">${formatText(file.name)}</span>
            <a class="${linkClasses}" ${linkAttributes} aria-label="${escapeHtml(ariaLabel)}">
              ${LINK_ICON}
            </a>
          </span>
        </div>`;
    }
  };

  function buildLogoSvg() {
    return `
      <svg class="logo__image" width="155" height="36" viewBox="0 0 155 36" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M143.801 36H91.3453C85.1665 36 80.1462 30.9677 80.1462 24.7742V11.2258C80.1462 5.03226 85.1665 0 91.3453 0H143.801C149.98 0 155 5.03226 155 11.2258V24.8387C155 30.9677 149.98 36 143.801 36Z" fill="#D9D9DF"/>
        <path d="M97.2662 24.1278V9.99872H94.2411V26.9665H104.153V24.1278H97.2662Z" fill="#323238"/>
        <path d="M140.325 19.6761C139.939 19.031 139.424 18.5149 138.78 18.1278C139.295 17.7407 139.681 17.2245 140.003 16.6439C140.389 15.9342 140.518 15.2245 140.518 14.4503C140.518 13.16 140.068 12.1278 139.102 11.289C138.137 10.4503 136.978 9.99872 135.562 9.99872H128.74V26.9665H135.755C137.236 26.9665 138.458 26.5149 139.488 25.5471C140.518 24.6439 141.033 23.4826 141.033 22.1278C140.969 21.2245 140.776 20.3858 140.325 19.6761ZM131.7 16.8374V12.8374H135.369C136.013 12.8374 136.463 13.031 136.914 13.4181C137.3 13.8052 137.493 14.2568 137.493 14.8374C137.493 15.4181 137.3 15.8697 136.914 16.2568C136.528 16.6439 136.013 16.8374 135.369 16.8374L131.7 16.8374ZM137.879 21.8697C137.879 22.5149 137.686 23.031 137.236 23.4181C136.785 23.8052 136.206 24.0632 135.562 24.0632H131.7V19.6761H135.562C136.27 19.6761 136.785 19.8697 137.236 20.3213C137.686 20.7084 137.879 21.2245 137.879 21.8697Z" fill="#323238"/>
        <path d="M121.596 26.967H125.007L122.883 23.2251H118.442L117.605 21.5476H121.982L121.531 20.7089H115.353L113.422 24.7089H120.244L121.596 26.967ZM115.288 14.5154C114.902 14.5154 114.516 14.9025 114.516 15.2896C114.516 15.7412 114.902 16.0638 115.288 16.0638C115.546 16.0638 115.803 15.9347 115.932 15.7412L115.288 14.5154ZM116.704 16.9025L116.189 15.9993C115.996 16.2573 115.674 16.3864 115.353 16.3864C114.773 16.3864 114.259 15.8702 114.259 15.2896C114.259 14.7735 114.645 14.3218 115.16 14.1928L114.773 13.4831C114.773 13.4831 112.199 15.2896 112.521 18.6444C112.521 18.6444 112.521 20.4509 113.937 21.9993L114.773 20.3864C113.551 18.9025 114.709 16.838 116.704 16.9025ZM119.343 17.4186L119.794 17.096L119.601 16.7089L117.477 17.9993L117.734 18.3218L118.12 18.1283L118.7 19.096L119.922 18.4509L119.343 17.4186ZM116.125 11.0315L114.387 12.0638L117.541 17.6122L119.408 16.5799L116.125 11.0315ZM115.353 10.5799L114.452 9.03152L113.422 9.61216L114.323 11.1605L113.808 11.4831L114.065 11.8702L116.189 10.6444L115.932 10.2573L115.353 10.5799Z" fill="#ED1064"/>
        <path d="M111.492 26.9675H108.081L111.942 19.2256C112.2 20.903 112.843 21.8062 113.616 22.7095L111.492 26.9675Z" fill="#323238"/>
        <path d="M66.2533 18.1434H60.5273L68.6936 29.9502H75.073L69.9234 22.5348C72.8825 21.1095 74.9385 18.1434 74.9385 14.6572C74.9385 9.82269 71.0187 5.95127 66.2533 5.95127H54.34V30.0273H59.5473V11.1132H66.2533C68.1748 11.1132 69.7313 12.654 69.7313 14.5994C69.7313 16.5447 68.1748 18.1434 66.2533 18.1434Z" fill="#ED1064"/>
        <path d="M12.3168 25.1158C8.39696 25.1158 5.2457 21.8992 5.2457 18.0278C5.2457 14.0986 8.4546 10.9398 12.3168 10.9398C14.2383 10.9398 16.0445 11.7103 17.3319 13.0007L22.347 10.805C20.0989 7.64622 16.4288 5.6431 12.2976 5.6431C5.53392 5.6431 0 11.1902 0 17.97C0 24.8076 5.53392 30.2969 12.2976 30.2969C16.4096 30.2969 20.0797 28.236 22.347 25.135L17.3319 23.0549C16.0445 24.3453 14.296 25.1158 12.3168 25.1158Z" fill="#ED1064"/>
        <path d="M44.0408 13.8289L42.2346 18.1434H39.4676L36.1819 25.8284L31.4165 14.6572L29.6872 18.1434H24.9219C24.9795 24.8461 30.5134 30.3355 37.2195 30.3355C43.9831 30.3355 49.4402 24.9232 49.5171 18.1434H45.847L44.0408 13.8289Z" fill="#ED1064"/>
        <path d="M31.551 9.95752L36.1242 20.8591L38.1226 16.2173H40.9472L43.9639 9.70713L46.9807 16.2173H49.3057C48.5371 10.2079 43.3875 5.6431 37.2002 5.6431C31.013 5.6431 25.8634 10.2272 25.0371 16.2173H28.5151L31.551 9.95752Z" fill="#ED1064"/>
      </svg>`;
  }

  function buildProfileSection(data) {
    const { profile, personalDocs } = data;
    const fields = [
      Template.field(t("lastName"), formatText(profile.lastName)),
      Template.field(t("firstName"), formatText(profile.firstName)),
      Template.field(t("middleName"), formatText(profile.middleName)),
      Template.field(t("birthYear"), formatText(profile.birthYear)),
      Template.field(t("gender"), formatText(profile.gender)),
      Template.field(t("phone"), formatText(profile.phone)),
      Template.field(t("workEmail"), formatText(profile.email))
    ].join("");

    const docFields = [
      Template.stackedField(t("passport"), formatText(personalDocs.passport)),
      Template.stackedField(t("taxId"), formatText(personalDocs.taxId)),
      Template.fileField(t("militaryDoc"), personalDocs.militaryDoc, t("militaryDocLink")),
      Template.stackedField(t("address"), formatText(personalDocs.address))
    ].join("");

    return `
      <section class="page">
        ${Template.logo()}
        <article class="card card--profile">
          <div class="card__photo" role="img" aria-label="${escapeHtml(profile.photoAlt)}">
            <img class="card__photo-image" src="${escapeHtml(profile.photoSrc)}" alt="${escapeHtml(profile.photoAlt)}">
          </div>
          <div class="card__fields">
            ${fields}
          </div>
        </article>
        <article class="card">
          ${docFields}
        </article>
      </section>`;
  }

  function buildWorkSection(data) {
    const { workplace, diploma } = data;
    const rows = [
      Template.stackedField(t("clinic"), formatText(workplace.clinic)),
      Template.stackedField(t("department"), formatText(workplace.department)),
      Template.stackedField(t("jobTitle"), formatText(workplace.jobTitle)),
      Template.stackedField(t("specialization"), formatText(workplace.specialization)),
      Template.stackedField(t("degree"), formatText(workplace.degree)),
      Template.stackedField(t("attestationDate"), formatDate(workplace.attestationDate)),
      Template.fileField(t("diplomaCopy"), diploma.file, t("diplomaLink")),
      Template.stackedField(t("date"), formatDate(diploma.date)),
      Template.stackedField(t("series"), formatText(diploma.series)),
      Template.stackedField(t("number"), formatText(diploma.number)),
      Template.stackedField(t("university"), formatText(diploma.university))
    ].join("");

    return `
      <section class="page">
        ${Template.logo()}
        <article class="card">
          ${rows}
        </article>
      </section>`;
  }

  function buildCertificateSection(data) {
    const { certificate } = data;
    const rows = [
      Template.fileField(t("specialistCertificate"), certificate.file, t("certificateLink")),
      Template.stackedField(t("date"), formatDate(certificate.date)),
      Template.stackedField(t("series"), formatText(certificate.series)),
      Template.stackedField(t("number"), formatText(certificate.number)),
      Template.stackedField(t("university"), formatText(certificate.university))
    ].join("");

    return `
      <section class="page">
        ${Template.logo()}
        <article class="card">
          ${rows}
        </article>
      </section>`;
  }

  function buildDocument(data) {
    return `
<!DOCTYPE html>
<html lang="${escapeHtml(ACTIVE_LANG)}">
  <head>
    <meta charset="UTF-8">
    <title>${escapeHtml(t("documentTitle"))}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="/static/COR_ID_css/doctor_preview.css">
  </head>
  <body class="doc">
    <main class="doc__pages">
      ${buildProfileSection(data)}
      ${buildWorkSection(data)}
      ${buildCertificateSection(data)}
    </main>
  </body>
</html>`;
  }

  function revokeObjectUrls(urls) {
    urls.forEach((url) => URL.revokeObjectURL(url));
  }

  window.exportFormToPDF = function exportFormToPDF() {
    const objectUrls = [];
    const previewData = collectPreviewData(objectUrls);
    const previewWindow = window.open("", "_blank");

    if (!previewWindow) {
      revokeObjectUrls(objectUrls);
      alert(t("popupBlocked"));
      return;
    }

    previewWindow.document.write(buildDocument(previewData));
    previewWindow.document.close();
    previewWindow.addEventListener("beforeunload", () => revokeObjectUrls(objectUrls));
  };
})();

