// admin_audit_excel.js
// Handles Download Excel for all audit sections

document.addEventListener('DOMContentLoaded', function() {
  // Audit summary Excel
  const auditBtn = document.getElementById('auditDownloadExcelBtn');
  if (auditBtn) {
    auditBtn.addEventListener('click', function() {
      window.open('/admin/api/audit-summary/excel', '_blank');
    });
  }
  // Transaction history Excel
  const txnBtn = document.getElementById('txnDownloadExcelBtn');
  if (txnBtn) {
    txnBtn.addEventListener('click', function() {
      window.open('/admin/api/audit-transactions/excel', '_blank');
    });
  }
  // Expense records Excel
  const expenseBtn = document.getElementById('expenseDownloadExcelBtn');
  if (expenseBtn) {
    expenseBtn.addEventListener('click', function() {
      window.open('/admin/api/audit-expenses/excel', '_blank');
    });
  }
});
