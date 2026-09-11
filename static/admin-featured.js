const featuredFieldSelector = 'input[type="checkbox"][name$="-is_featured"]';

document.addEventListener('change', (event) => {
  const selected = event.target.closest(featuredFieldSelector);
  if (!selected?.checked) return;

  document.querySelectorAll(featuredFieldSelector).forEach((field) => {
    if (field !== selected && field.checked) {
      field.checked = false;
      field.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
});
