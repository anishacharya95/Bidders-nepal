(function () {
  'use strict';
  var KEY = 'bn_saved_tenders';

  function readIds() {
    try {
      var value = JSON.parse(localStorage.getItem(KEY) || '[]');
      return Array.isArray(value) ? value.map(Number).filter(function (id) { return id > 0; }) : [];
    } catch (error) {
      return [];
    }
  }

  function writeIds(ids) {
    try {
      localStorage.setItem(KEY, JSON.stringify(ids));
    } catch (error) {
      /* storage unavailable: saving is best-effort */
    }
  }

  function paintCount() {
    var count = readIds().length;
    document.querySelectorAll('[data-saved-count]').forEach(function (el) {
      el.textContent = count ? '(' + count + ')' : '';
    });
  }

  function paintButtons() {
    var ids = readIds();
    document.querySelectorAll('[data-tender-save]').forEach(function (button) {
      var id = Number(button.getAttribute('data-tender-save'));
      var saved = ids.indexOf(id) !== -1;
      button.textContent = saved ? 'Saved ✓' : 'Save tender';
      button.setAttribute('aria-pressed', saved ? 'true' : 'false');
      button.classList.toggle('is-saved', saved);
    });
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-tender-save]');
    if (!button) return;
    var id = Number(button.getAttribute('data-tender-save'));
    if (!id) return;
    var ids = readIds();
    var index = ids.indexOf(id);
    if (index === -1) ids.push(id);
    else ids.splice(index, 1);
    writeIds(ids);
    paintCount();
    paintButtons();
  });

  document.addEventListener('DOMContentLoaded', function () {
    paintCount();
    paintButtons();
  });
})();
