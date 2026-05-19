document.querySelectorAll('.service-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    btn.closest('.service-section').classList.toggle('open');
  });
});

document.addEventListener('click', e => {
  const btn = e.target.closest('[data-expand]');
  if (!btn) return;
  const overview = btn.previousElementSibling;
  document.querySelectorAll('.card-overview.expanded').forEach(el => {
    if (el !== overview) {
      el.classList.remove('expanded');
      el.nextElementSibling.textContent = 'more';
    }
  });
  const isExpanded = overview.classList.toggle('expanded');
  btn.textContent = isExpanded ? 'less' : 'more';
});

document.querySelectorAll('.card img').forEach(img => {
  img.addEventListener('error', function () {
    this.src = 'https://via.placeholder.com/155x230?text=No+Image';
  });
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-drag-scroll]').forEach(row => {
    let isDown = false; let startX; let scrollLeft;
    row.addEventListener('mousedown', (e) => { isDown = true; startX = e.pageX - row.offsetLeft; scrollLeft = row.scrollLeft; });
    row.addEventListener('mouseleave', () => { isDown = false; });
    row.addEventListener('mouseup', () => { isDown = false; });
    row.addEventListener('mousemove', (e) => {
      if(!isDown) return;
      e.preventDefault();
      const x = e.pageX - row.offsetLeft;
      const walk = (x - startX) * 2;
      row.scrollLeft = scrollLeft - walk;
    });
  });
});