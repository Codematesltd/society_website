// Floating Query Box and Civil Score Box functionality
function initializeFloatingBoxes() {
  // Query Box functionality
  const queryBtn = document.getElementById('queryBtn');
  const queryBox = document.getElementById('queryBox');
  const closeQuery = document.getElementById('closeQuery');
  const sendQuery = document.getElementById('sendQuery');

  queryBtn.addEventListener('click', () => {
    queryBox.classList.remove('hidden');
    setTimeout(() => queryBox.classList.add('show'), 10);
  });
  
  closeQuery.addEventListener('click', () => {
    queryBox.classList.remove('show');
    setTimeout(() => queryBox.classList.add('hidden'), 400);
  });
  
  sendQuery.addEventListener('click', () => {
    alert("✅ Your query has been sent successfully!");
    queryBox.classList.remove('show');
    setTimeout(() => queryBox.classList.add('hidden'), 400);
  });

  // Civil Score Box functionality
  const civilBtn = document.getElementById('civilBtn');
  const civilBox = document.getElementById('civilBox');
  const closeCivil = document.getElementById('closeCivil');
  const checkCivil = document.getElementById('checkCivil');

  civilBtn.addEventListener('click', () => {
    civilBox.classList.remove('hidden');
    setTimeout(() => civilBox.classList.add('show'), 10);
  });
  
  closeCivil.addEventListener('click', () => {
    civilBox.classList.remove('show');
    setTimeout(() => civilBox.classList.add('hidden'), 400);
  });
  
  checkCivil.addEventListener('click', () => {
    alert("📊 Civil score checked successfully!");
    civilBox.classList.remove('show');
    setTimeout(() => civilBox.classList.add('hidden'), 400);
  });
}
