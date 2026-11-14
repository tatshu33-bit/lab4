// Валідація форм на стороні клієнта + підтвердження небезпечних дій
(function () {
  const msg = (el) => el.dataset.msg || el.validationMessage;
  function setError(el, text) {
    let e = el.parentElement.querySelector('.err');
    if (!text) { el.classList.remove('invalid'); if (e) e.remove(); return; }
    el.classList.add('invalid');
    if (!e) { e = document.createElement('span'); e.className = 'err'; el.parentElement.appendChild(e); }
    e.textContent = text;
  }
  function check(el) {
    if (el.dataset.match) {                                  // «повторіть пароль»
      const other = el.form.elements[el.dataset.match];
      el.setCustomValidity(el.value !== other.value ? 'Значення не співпадають' : '');
    }
    if (el.type === 'text' && el.hasAttribute('required') && !el.value.trim()) el.setCustomValidity('Поле обов\'язкове');
    else if (!el.dataset.match) el.setCustomValidity('');
    setError(el, el.checkValidity() ? '' : msg(el));
    return el.checkValidity();
  }
  document.querySelectorAll('form[data-validate]').forEach((form) => {
    const fields = () => [...form.elements].filter((el) => el.willValidate && el.name !== '_csrf');
    fields().forEach((el) => { el.addEventListener('blur', () => check(el)); el.addEventListener('input', () => el.classList.contains('invalid') && check(el)); });
    form.addEventListener('submit', (ev) => {
      let ok = true; fields().forEach((el) => { if (!check(el)) ok = false; });
      if (!ok) { ev.preventDefault(); const bad = form.querySelector('.invalid'); bad && bad.focus(); }
    });
  });
  document.querySelectorAll('form[data-confirm]').forEach((f) =>
    f.addEventListener('submit', (ev) => { if (!confirm(f.dataset.confirm)) ev.preventDefault(); }));
})();
