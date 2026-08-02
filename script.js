const menuButton = document.querySelector('.menu-button');
menuButton.addEventListener('click', () => {
  const expanded = menuButton.getAttribute('aria-expanded') === 'true';
  menuButton.setAttribute('aria-expanded', String(!expanded));
  menuButton.firstChild.textContent = expanded ? 'MENU ' : 'CLOSE ';
  document.body.classList.toggle('menu-open', !expanded);
});
