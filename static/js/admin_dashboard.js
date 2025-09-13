// admin_dashboard.js
// Handles Recent Transactions Excel download for admin dashboard

document.addEventListener('DOMContentLoaded', function() {
  const ySel = document.getElementById('rtYear');
  const mSel = document.getElementById('rtMonth');
  const dSel = document.getElementById('rtDay');
  const excelBtn = document.getElementById('rtDownloadExcelBtn');
  if (excelBtn) {
    excelBtn.addEventListener('click', function() {
      const qs = new URLSearchParams();
      if (ySel && ySel.value) qs.set('year', ySel.value);
      if (mSel && mSel.value) qs.set('month', mSel.value);
      if (dSel && dSel.value) qs.set('day', dSel.value);
      const url = `/admin/api/recent-transactions/excel${qs.toString() ? ('?' + qs.toString()) : ''}`;
      window.open(url, '_blank');
    });
  }
});
