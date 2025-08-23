function initializeFloatingBoxes() {
  // Query floating box
  const queryBtn = document.getElementById('queryBtn');
  const queryBox = document.getElementById('queryBox');
  const closeQuery = document.getElementById('closeQuery');
  if (queryBtn && queryBox) {
    queryBtn.addEventListener('click', () => {
      queryBox.classList.toggle('hidden');
      queryBox.classList.toggle('show');
    });
  }
  if (closeQuery && queryBox) {
    closeQuery.addEventListener('click', () => {
      queryBox.classList.add('hidden');
      queryBox.classList.remove('show');
    });
  }
  // Civil Score floating box
  const civilBtn = document.getElementById('civilBtn');
  const civilBox = document.getElementById('civilBox');
  const closeCivil = document.getElementById('closeCivil');
  if (civilBtn && civilBox) {
    civilBtn.addEventListener('click', () => {
      civilBox.classList.toggle('hidden');
      civilBox.classList.toggle('show');
    });
  }
  if (closeCivil && civilBox) {
    closeCivil.addEventListener('click', () => {
      civilBox.classList.add('hidden');
      civilBox.classList.remove('show');
    });
  }
}
