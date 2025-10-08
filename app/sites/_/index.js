document.addEventListener('DOMContentLoaded', () => {
  window.__siteLoaded = 'root';
  const banner = document.createElement('div');
  banner.id = 'root-status';
  banner.textContent = 'Root script loaded';
  document.body.appendChild(banner);
});
