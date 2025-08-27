(function(){
  const cfg = window.STAFF_DASHBOARD_CONFIG || {};
  /* ================= JWT Heartbeat ================= */
  function redirectToLogin(){
    try{ sessionStorage.removeItem('authToken'); }catch(e){}
    if (cfg.loginUrl) window.location.replace(cfg.loginUrl);
  }
  async function validateToken(){
    let token = null;
    try { token = sessionStorage.getItem('authToken'); } catch(e){}
    if (!token){ redirectToLogin(); return; }
    try{
      const res = await fetch('/auth/validate-token',{
        method:'POST',
        headers:{
          'Content-Type':'application/json',
          'Authorization':`Bearer ${token}`
        },
        credentials:'include',
        body: JSON.stringify({ token })
      });
      if (res.status === 401) redirectToLogin();
    }catch(e){}
  }
  async function refreshToken(){
    try{
      const res = await fetch('/auth/refresh-token',{ method:'POST', credentials:'include' });
      if (res.status === 401){ redirectToLogin(); return; }
      const data = await res.json().catch(()=>null);
      if (data && data.status==='success' && data.token){
        try{ sessionStorage.setItem('authToken', data.token); }catch(e){}
      }
    }catch(e){}
  }
  validateToken();
  setInterval(validateToken, 10000);
  setInterval(refreshToken, 4*60*1000);
  document.addEventListener('DOMContentLoaded', ()=>{
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.addEventListener('click', ()=>{ try{ sessionStorage.removeItem('authToken'); }catch(e){} });
  });

  /* ================= Navigation / Section Loader ================= */
  document.addEventListener('DOMContentLoaded', () => {
    const sections = document.querySelectorAll('.dynamic-section');
    const buttons = document.querySelectorAll('.nav-button');
    const homeBtn = document.getElementById('homeBtn');
    function showSection(id){
      sections.forEach(sec=>sec.classList.add('hidden'));
      const target = document.getElementById(id);
      if (target){
        target.classList.remove('hidden');
        const content = target.querySelector('.content');
        const loader = target.querySelector('.loader');
        if (content && loader){
          content.classList.add('hidden');
          loader.classList.remove('hidden');
          setTimeout(()=>{
            loader.classList.add('hidden');
            content.classList.remove('hidden');
          },400);
        }
      }
    }
    buttons.forEach(btn=>{
      btn.addEventListener('click', ()=> showSection(btn.dataset.target));
    });
    if (homeBtn){
      homeBtn.addEventListener('click', e=>{
        e.preventDefault();
        showSection('dashboardSummary');
      });
    }
    showSection('dashboardSummary');
  });

  /* ================= Dashboard Stats ================= */
  async function fetchDashboardStats(){
    try{
      const res = await fetch('/staff/api/dashboard-stats');
      const data = await res.json();
      if (!res.ok || data.status!=='success') return;
      const totalCustomersEl = document.getElementById('totalCustomers');
      const activeLoansEl = document.getElementById('activeLoans');
      const totalAmountEl = document.getElementById('totalAmount');
      if (totalCustomersEl) totalCustomersEl.textContent = data.total_customers ?? 0;
      if (activeLoansEl) activeLoansEl.textContent = data.active_loans ?? 0;
      if (totalAmountEl) totalAmountEl.textContent = '₹' + Number(data.total_balance||0).toLocaleString();
    }catch(e){}
  }
  document.addEventListener('DOMContentLoaded', fetchDashboardStats);

  /* ================= Customer Account Info Search ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const form = document.getElementById('customerSearchForm');
    if (!form) return;
    form.addEventListener('submit', async e=>{
      e.preventDefault();
      const customerId = document.getElementById('kgidInput').value.trim();
      const resultDiv = document.getElementById('customerInfoResult');
      resultDiv.innerHTML = '<div class="text-blue-600">Loading...</div>';
      try{
        const res = await fetch(`/staff/api/fetch-account?customer_id=${encodeURIComponent(customerId)}`);
        const data = await res.json().catch(()=>null);
        if (!res.ok || !data || data.status!=='success'){
          resultDiv.innerHTML = `<div class="text-red-600">${(data && data.message) || 'Error fetching data.'}</div>`;
          return;
        }
        const m = data;
        const salaryText = (m.salary!==null && m.salary!==undefined && m.salary!=='') ? '₹'+Number(m.salary).toLocaleString() : '-';
        const balanceText = (m.balance!==null && m.balance!==undefined && m.balance!=='') ? '₹'+Number(m.balance).toLocaleString() : '-';
        resultDiv.innerHTML = `
          <div class="max-w-3xl mx-auto bg-white p-6 rounded-xl shadow border">
            <div class="flex flex-col md:flex-row gap-6 items-start">
              <div class="flex-1 space-y-2 text-sm">
                <div><strong>Name:</strong> ${m.name ?? '-'}</div>
                <div><strong>KGID:</strong> ${m.kgid ?? '-'}</div>
                <div><strong>Phone:</strong> ${m.phone ?? '-'}</div>
                <div><strong>Email:</strong> ${m.email ?? '-'}</div>
                <div><strong>Salary:</strong> ${salaryText}</div>
                <div><strong>Organization:</strong> ${m.organization_name ?? '-'}</div>
                <div><strong>Address:</strong> ${m.address ?? '-'}</div>
                <div><strong>Balance:</strong> ${balanceText}</div>
                <div><strong>Customer ID:</strong> ${m.customer_id ?? '-'}</div>
                <div><strong>Status:</strong> ${m.status ?? '-'}</div>
              </div>
              <div class="w-full md:w-64 flex flex-col items-center gap-4">
                <div class="w-28 h-28 rounded-full overflow-hidden ring-2 ring-blue-200 bg-gray-50 flex items-center justify-center">
                  ${m.photo_url ? `<img src="${m.photo_url}" alt="Photo" class="w-full h-full object-cover"/>` : '<span class="text-gray-400 text-xs">No Photo</span>'}
                </div>
                <div class="w-full">
                  <div class="text-xs text-gray-500 mb-1">Signature</div>
                  <div class="border rounded p-2 bg-gray-50 flex items-center justify-center min-h-[80px]">
                    ${m.signature_url ? `<img src="${m.signature_url}" alt="Signature" class="max-h-24 object-contain"/>` : '<span class="text-gray-400 text-xs">No Signature</span>'}
                  </div>
                </div>
              </div>
            </div>
          </div>`;
      }catch{
        resultDiv.innerHTML = `<div class="text-red-600">Network error.</div>`;
      }
    });
  });

  /* ================= Loan Apply (Multi-Step) ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const toStep2Btn = document.getElementById('toStep2Btn');
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const step3 = document.getElementById('step3');
    const loanFormError = document.getElementById('loanFormError');
    if (toStep2Btn && step1 && step2){
      toStep2Btn.addEventListener('click', ()=>{
        const selectedLoanType = document.querySelector('input[name="loanType"]:checked');
        if (!selectedLoanType){
          if (loanFormError) loanFormError.textContent = "Please select a loan type.";
          return;
        }
        if (loanFormError) loanFormError.textContent = "";
        step1.classList.add('hidden');
        step2.classList.remove('hidden');
        if (step3) step3.classList.add('hidden');
      });
    }
    const loanAccountNumberInput = document.getElementById('loanAccountNumber');
    const fetchAccountBtn = document.getElementById('fetchAccountBtn');
    const accountFetchMsg = document.getElementById('accountFetchMsg');
    if (fetchAccountBtn){
      fetchAccountBtn.addEventListener('click', async ()=>{
        const raw = loanAccountNumberInput.value.trim();
        if (!raw){
          accountFetchMsg.textContent = "Please enter a Customer ID or KGID.";
          return;
        }
        accountFetchMsg.textContent = "Fetching details...";
        try{
          let data=null;
            let res = await fetch(`/staff/api/fetch-account?customer_id=${encodeURIComponent(raw)}`);
            try{ data = await res.json(); }catch{}
            if (!res.ok || !data || data.status!=='success' || !data.name){
              res = await fetch(`/loan/fetch-account?customer_id=${encodeURIComponent(raw)}`);
              try{ data = await res.json(); }catch{}
            }
            if ((!res.ok || !data || data.status!=='success' || !data.name) && /^[A-Za-z]{3,}\d{3,}$/.test(raw) === false){
              const kgRes = await fetch(`/staff/api/customer?kgid=${encodeURIComponent(raw)}`);
              let kgData=null; try{ kgData = await kgRes.json(); }catch{}
              if (kgRes.ok && kgData && kgData.name){
                data = { status:'success', name:kgData.name, kgid:kgData.kgid, customer_id:kgData.customer_id };
                res = { ok:true };
              }
            }
            if (res.ok && data && data.status==='success' && data.name){
              document.getElementById('loanName').value = data.name;
              document.getElementById('loanKGID').value = data.kgid || '';
              document.getElementById('loanAccount').value = data.customer_id || raw;
              loanAccountNumberInput.value = data.customer_id || raw;
              accountFetchMsg.textContent = "";
              const nextBtn = document.getElementById('toStep2Btn');
              if (nextBtn) nextBtn.classList.add('hidden');
              if (step3.classList.contains('hidden')){
                step3.classList.remove('hidden');
                step2.classList.add('hidden');
                step1.classList.remove('hidden');
              }
            } else {
              accountFetchMsg.textContent = "Account not found.";
            }
        }catch{
          accountFetchMsg.textContent = "Network error.";
        }
      });
    }
    /* Surety checks */
    function setupSuretyCheck(checkBtnId, kgidInputId, msgId){
      const checkBtn = document.getElementById(checkBtnId);
      const kgidInput = document.getElementById(kgidInputId);
      const msgDiv = document.getElementById(msgId);
      const removeBtn = document.getElementById(checkBtnId.replace('check','remove'));
      function preloadSurety(data){
        const fieldsDiv = document.getElementById(
          checkBtnId === 'checkSurety1Btn' ? 'surety1Fields' : 'surety2Fields'
        );
        fieldsDiv.innerHTML = '';
        if (data.available){
          msgDiv.textContent = '';
          fieldsDiv.innerHTML = `
            <div><label class="block font-medium mb-1">KGID</label>
              <input type="text" value="${kgidInput.value}" readonly class="w-full px-4 py-2 border rounded bg-gray-100"/>
            </div>
            <div><label class="block font-medium mb-1">Name</label>
              <input type="text" value="${data.member.name||''}" readonly class="w-full px-4 py-2 border rounded bg-gray-100"/>
            </div>
            <div><label class="block font-medium mb-1">Phone</label>
              <input type="text" value="${data.member.phone||''}" readonly class="w-full px-4 py-2 border rounded bg-gray-100"/>
            </div>`;
        } else if (data.active_loan_count >= 2){
          msgDiv.textContent = "This surety is already backing 2 active loans.";
        } else {
          msgDiv.textContent = data.reason || "Surety not found.";
        }
      }
      if (checkBtn){
        checkBtn.addEventListener('click', async ()=>{
          const kgid = kgidInput.value.trim();
          msgDiv.textContent = "Checking surety...";
          try{
            const res = await fetch(`/loan/check-surety?customer_id=${encodeURIComponent(kgid)}`);
            if (res.ok){
              const data = await res.json();
              const sObj = {
                available: !!data.available,
                member: data.member || {},
                active_loan_count: data.active_loan_count || 0
              };
              preloadSurety(sObj);
              if (sObj.available && sObj.active_loan_count < 2){
                checkBtn.disabled = true;
                kgidInput.disabled = true;
                if (removeBtn) removeBtn.classList.remove('hidden');
              }
            } else {
              msgDiv.textContent = "Error checking surety.";
            }
          }catch{
            msgDiv.textContent = "Network error.";
          }
        });
      }
      if (removeBtn){
        removeBtn.addEventListener('click', ()=>{
          msgDiv.textContent = "";
          kgidInput.value = "";
          kgidInput.disabled = false;
          checkBtn.disabled = false;
          removeBtn.classList.add('hidden');
          const fieldsDiv = document.getElementById(
            checkBtnId === 'checkSurety1Btn' ? 'surety1Fields' : 'surety2Fields'
          );
          if (fieldsDiv) fieldsDiv.innerHTML = '';
        });
      }
    }
    setupSuretyCheck('checkSurety1Btn','surety1KGID','surety1Msg');
    setupSuretyCheck('checkSurety2Btn','surety2KGID','surety2Msg');
    /* Terms / Form readiness */
    const termsCheckbox = document.getElementById('termsCheckbox');
    const applyLoanBtn = document.getElementById('applyLoanBtn');
    if (termsCheckbox && applyLoanBtn){
      termsCheckbox.checked = false;
      termsCheckbox.disabled = false;
      termsCheckbox.required = true;
      function checkFormReady(){
        const requiredIds = ['loanName','loanAccount','loanKGID','loanAmount','loanInterest','loanTenure','loanPurpose','surety1KGID','surety2KGID'];
        let allFilled = requiredIds.every(id=>{
          const el = document.getElementById(id);
            return el && el.value.trim() !== '';
        });
        applyLoanBtn.disabled = !(allFilled && termsCheckbox.checked);
      }
      const reqIds = ['loanName','loanAccount','loanKGID','loanAmount','loanInterest','loanTenure','loanPurpose','surety1KGID','surety2KGID'];
      reqIds.forEach(id=>{
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', checkFormReady);
      });
      termsCheckbox.addEventListener('change', checkFormReady);
      checkFormReady();
    }
    /* Loan submission */
    const loanStepForm = document.getElementById('loanStepForm');
    if (loanStepForm){
      loanStepForm.addEventListener('submit', async e=>{
        e.preventDefault();
        const errorDiv = document.getElementById('loanFormError');
        errorDiv.textContent = '';
        const loanTypeEl = document.querySelector('input[name="loanType"]:checked');
        const loan_type = loanTypeEl ? loanTypeEl.value : null;
        const customerId = (document.getElementById('loanAccount')?.value.trim()) ||
                           (document.getElementById('loanAccountNumber')?.value.trim());
        const loan_amount = document.getElementById('loanAmount')?.value;
        const interest_rate = document.getElementById('loanInterest')?.value;
        const loan_term_months = document.getElementById('loanTenure')?.value;
        const purpose_input = document.getElementById('loanPurpose')?.value || '';
        const sureties = [];
        const s1 = document.getElementById('surety1KGID')?.value;
        const s2 = document.getElementById('surety2KGID')?.value;
        if (s1 && s1.trim()) sureties.push(s1.trim());
        if (s2 && s2.trim()) sureties.push(s2.trim());
        if (!loan_type || !customerId || !loan_amount || !interest_rate || !loan_term_months || sureties.length===0){
          errorDiv.textContent = "Please fill all required fields and add at least one surety.";
          return;
        }

        // --- Spinner UI start ---
        const applyBtn = document.getElementById('applyLoanBtn');
        let originalBtnHTML = null;
        if (applyBtn){
          originalBtnHTML = applyBtn.innerHTML;
          applyBtn.disabled = true;
          applyBtn.setAttribute('aria-busy','true');
          applyBtn.innerHTML = `
            <span class="flex items-center justify-center gap-2">
              <svg class="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24" fill="none">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor"
                  d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
              </svg>
              Submitting...
            </span>`;
        }
        // --- Spinner UI end ---

        const payload = {
          loan_type,
          customer_id: customerId,
          loan_amount: Number(loan_amount),
          interest_rate: Number(interest_rate),
          loan_term_months: Number(loan_term_months),
          sureties
        };
        if (loan_type==='normal') payload.purpose_of_loan = purpose_input;
        if (loan_type==='emergency') payload.purpose_of_emergency_loan = purpose_input;
        try{
          const headers = { 'Content-Type':'application/json' };
          if (window.STAFF_EMAIL) headers['X-Staff-Email'] = window.STAFF_EMAIL;
          const res = await fetch('/loan/apply',{
            method:'POST',
            headers,
            credentials:'include',
            body: JSON.stringify(payload)
          });
          const data = await res.json().catch(()=>null);
          if (res.ok && data && data.status==='success'){
            const loanId = data.loan_id;
            let loanDetails=null;
            try{
              const loanRes = await fetch(`/loan/${encodeURIComponent(loanId)}`, { credentials:'include' });
              if (loanRes.ok) loanDetails = await loanRes.json().catch(()=>null);
            }catch{}
            const successPopup = document.getElementById('loanSuccessPopup');
            if (successPopup){
              const popupContent = successPopup.querySelector('div.text-lg.font-bold.mb-2');
              const certLink = data.certificate_url ? `<a href="${data.certificate_url}" target="_blank" class="text-blue-600 underline">View Certificate</a>` : '';
              const staffInfo = loanDetails && loanDetails.staff ? `${loanDetails.staff.name||''} ${loanDetails.staff.phone? '('+loanDetails.staff.phone+')':''}` : '';
              if (popupContent){
                popupContent.innerHTML = `
                  Loan Application Submitted Successfully!<br>
                  <span class='text-blue-600'>Loan ID: ${loanId || 'N/A'}</span><br>
                  ${certLink ? certLink + '<br>' : ''}
                  ${staffInfo ? `<span class="text-sm text-gray-700">Processed by: ${staffInfo}</span>` : ''}`;
              }
              successPopup.classList.remove('hidden');
              setTimeout(()=>{
                successPopup.classList.add('hidden');
                loanStepForm.reset();
                step1.classList.remove('hidden');
                step2.classList.add('hidden');
                step3.classList.add('hidden');
              },3500);
            }
          } else {
            errorDiv.textContent = (data && (data.message||data.error)) || 'Loan application failed.';
          }
        }catch{
          errorDiv.textContent = 'Network error.';
        }finally{
          if (applyBtn){
            applyBtn.disabled = false;
            applyBtn.removeAttribute('aria-busy');
            if (originalBtnHTML) applyBtn.innerHTML = originalBtnHTML;
          }
        }
      });
    }
  });

  /* ================= Transaction Modal (Get Transaction) ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const fetchTransBtn = document.getElementById('fetchTransBtn');
    const transSTIDInput = document.getElementById('transSTID');
    const transResultDiv = document.getElementById('transResult');
    const transInputPanel = document.getElementById('transInputPanel');
    const transactionModal = document.getElementById('transactionModal');
    const getTransactionBtn = document.getElementById('getTransactionBtn');
    const closeTransModal = document.getElementById('closeTransModal');
    if (fetchTransBtn){
      fetchTransBtn.addEventListener('click', ()=>{
        const stid = transSTIDInput.value.trim();
        if (!stid){
          transResultDiv.innerHTML = '<div class="text-red-600">Enter a valid STID</div>';
          return;
        }
        window.open(`/staff/transaction/certificate/${encodeURIComponent(stid)}`,'_blank');
        transactionModal.classList.add('hidden');
      });
    }
    if (getTransactionBtn){
      getTransactionBtn.addEventListener('click', ()=>{
        transactionModal.classList.remove('hidden');
        transInputPanel.style.display='block';
        transResultDiv.innerHTML='';
        transSTIDInput.value='';
      });
    }
    if (closeTransModal && transactionModal){
      closeTransModal.addEventListener('click', ()=> transactionModal.classList.add('hidden'));
    }
  });

  /* ================= Mail Notification Modal (dummy) ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const mailNotificationBtn = document.getElementById('mailNotificationBtn');
    const mailModal = document.getElementById('mailModal');
    const closeMailModal = document.getElementById('closeMailModal');
    if (mailNotificationBtn && mailModal){
      mailNotificationBtn.addEventListener('click', ()=> mailModal.classList.remove('hidden'));
    }
    if (closeMailModal && mailModal){
      closeMailModal.addEventListener('click', ()=> mailModal.classList.add('hidden'));
    }
  });

  /* ================= Add User (OTP Email Verification) ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const verifyBtn = document.getElementById('verifyEmailBtn');
    const otpContainer = document.getElementById('otpContainer');
    const otpInput = document.getElementById('otpInput');
    const warning = document.getElementById('verifyWarning');
    const addUserBtn = document.getElementById('addUserBtn');
    const addUserForm = document.getElementById('addUserForm');
    const addUserMsg = document.getElementById('addUserMsg');
    const emailInput = document.getElementById('emailInput');
    if (!verifyBtn || !addUserForm) return;
    let otpSent=false, otpVerified=false;
    verifyBtn.addEventListener('click', async ()=>{
      const email = emailInput.value.trim();
      if (!email){
        addUserMsg.textContent = "Please enter an email.";
        return;
      }
      verifyBtn.disabled = true;
      addUserMsg.textContent = "Sending OTP...";
      try{
        const formData = new FormData();
        formData.append('email', email);
        const res = await fetch('/staff/api/add-member/send-otp',{ method:'POST', body: formData });
        let data; try{ data = await res.json(); }catch{
          addUserMsg.textContent="Server error. Please check backend logs.";
          verifyBtn.disabled=false;
          return;
        }
        if (data.status==='success'){
          otpContainer.classList.remove('hidden');
            otpInput.focus();
          addUserMsg.textContent = "OTP sent to email. Enter OTP to continue.";
          otpSent = true;
        } else {
          addUserMsg.textContent = data.message || "Failed to send OTP.";
          verifyBtn.disabled = false;
        }
      }catch{
        addUserMsg.textContent = "Network error.";
        verifyBtn.disabled = false;
      }
    });
    if (otpInput){
      otpInput.addEventListener('input', ()=>{
        if (otpInput.value.length === 6){
          otpVerified = true;
          otpInput.classList.add('border-green-500');
          addUserMsg.textContent="";
        } else {
          otpVerified = false;
          otpInput.classList.remove('border-green-500');
        }
      });
    }
    addUserForm.addEventListener('submit', async e=>{
      e.preventDefault();
      if (!otpSent || !otpVerified){
        warning.classList.remove('hidden');
        addUserMsg.textContent = "Please verify your email and enter OTP.";
        addUserMsg.className = "mb-4 text-center bg-red-100 text-red-700 px-4 py-2 rounded shadow";
        addUserMsg.classList.remove('hidden');
        return;
      }
      warning.classList.add('hidden');
      addUserMsg.textContent = "Submitting user...";
      addUserMsg.className = "mb-4 text-center bg-blue-100 text-blue-700 px-4 py-2 rounded shadow";
      addUserMsg.classList.remove('hidden');
      const formData = new FormData(addUserForm);
      try{
        const res = await fetch('/staff/api/add-member',{ method:'POST', body: formData });
        const data = await res.json();
        if (data.status==='success'){
          addUserMsg.textContent = "User added successfully!";
          addUserMsg.className = "mb-4 text-center bg-green-100 text-green-700 px-4 py-2 rounded shadow";
          addUserForm.reset();
          otpContainer.classList.add('hidden');
          verifyBtn.disabled = false;
          otpSent=false; otpVerified=false;
        } else {
          addUserMsg.textContent = data.message || "Failed to add user.";
          addUserMsg.className = "mb-4 text-center bg-red-100 text-red-700 px-4 py-2 rounded shadow";
        }
      }catch{
        addUserMsg.textContent = "Network error.";
        addUserMsg.className = "mb-4 text-center bg-red-100 text-red-700 px-4 py-2 rounded shadow";
      }
    });
  });

  /* ================= Expense Download Placeholder ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const downloadReportBtn = document.getElementById('downloadReportBtn');
    if (downloadReportBtn){
      downloadReportBtn.addEventListener('click', ()=> alert("Report download functionality will be implemented here."));
    }
  });

  // --- Add a reusable modal for showing messages if not present ---
  function ensureMessageModal() {
    if (!document.getElementById('dashboardMsgModal')) {
      const modal = document.createElement('div');
      modal.id = 'dashboardMsgModal';
      modal.className = 'fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 hidden';
      modal.innerHTML = `
        <div class="bg-white p-8 rounded-xl shadow-xl w-full max-w-sm text-center">
          <div id="dashboardMsgModalIcon" class="text-4xl mb-2"></div>
          <div id="dashboardMsgModalText" class="mb-4 text-lg"></div>
          <button id="dashboardMsgModalClose" class="px-6 py-2 bg-blue-600 text-white rounded shadow">OK</button>
        </div>
      `;
      document.body.appendChild(modal);
    }
    // Always re-bind the close button to hide the modal
    const modal = document.getElementById('dashboardMsgModal');
    const closeBtn = document.getElementById('dashboardMsgModalClose');
    if (closeBtn) {
      closeBtn.onclick = () => {
        modal.classList.add('hidden');
      };
    }
  }
  function showDashboardMsgModal(msg, type) {
    ensureMessageModal();
    const modal = document.getElementById('dashboardMsgModal');
    const icon = document.getElementById('dashboardMsgModalIcon');
    const text = document.getElementById('dashboardMsgModalText');
    icon.innerHTML = type === 'success'
      ? '<span class="text-green-600">✔</span>'
      : type === 'error'
        ? '<span class="text-red-600">✖</span>'
        : '';
    text.textContent = msg;
    modal.classList.remove('hidden');
  }

  /* ================= Deposit / Withdraw Transactions ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const depositForm = document.getElementById('depositForm');
    const withdrawForm = document.getElementById('withdrawForm');
    const depositBtnToggle = document.getElementById('showDepositBtn');
    const withdrawBtnToggle = document.getElementById('showWithdrawBtn');
    function toggleForms(showDeposit){
      if (showDeposit){
        depositForm.classList.remove('hidden');
        withdrawForm.classList.add('hidden');
        depositBtnToggle.classList.add('bg-green-500','text-white');
        depositBtnToggle.classList.remove('bg-gray-300');
        withdrawBtnToggle.classList.add('bg-gray-300');
        withdrawBtnToggle.classList.remove('bg-red-500','text-white');
      } else {
        withdrawForm.classList.remove('hidden');
        depositForm.classList.add('hidden');
        withdrawBtnToggle.classList.add('bg-red-500','text-white');
        withdrawBtnToggle.classList.remove('bg-gray-300');
        depositBtnToggle.classList.add('bg-gray-300');
        depositBtnToggle.classList.remove('bg-green-500','text-white');
      }
    }
    if (depositBtnToggle) depositBtnToggle.addEventListener('click', ()=> toggleForms(true));
    if (withdrawBtnToggle) withdrawBtnToggle.addEventListener('click', ()=> toggleForms(false));
    function formValues(prefix){
      return {
        customer_id: document.getElementById(prefix+'CustomerId')?.value.trim(),
        amount: document.getElementById(prefix+'Amount')?.value.trim(),
        date: document.getElementById(prefix+'Date')?.value.trim(),
        from_account: document.getElementById(prefix+'FromAccount')?.value.trim(),
        from_bank_name: document.getElementById(prefix+'FromBank')?.value.trim(),
        to_account: document.getElementById(prefix+'ToAccount')?.value.trim(),
        to_bank_name: document.getElementById(prefix+'ToBank')?.value.trim(),
        transaction_id: document.getElementById(prefix+'TxnId')?.value.trim(),
        remarks: document.getElementById(prefix+'Remarks')?.value.trim()
      };
    }
    const depositBtn = document.getElementById('depositBtn');
    if (depositBtn){
      depositBtn.addEventListener('click', async ()=>{
        const d = formValues('deposit');
        const requiredFields = Object.assign({}, d);
        delete requiredFields.remarks;
        if (Object.values(requiredFields).some(v => v==='' ) || !d.date){
          showDashboardMsgModal("Please fill all Deposit fields.", "error");
          return;
        }
        d.type='deposit';
        // --- Spinner animation ---
        const origHTML = depositBtn.innerHTML;
        depositBtn.disabled = true;
        depositBtn.innerHTML = `<span class="inline-flex items-center gap-2"><svg class="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>Processing...</span>`;
        try{
          const fd = new FormData();
          Object.entries(d).forEach(([k,v])=> fd.append(k,v));
          const res = await fetch('/staff/api/add-transaction',{ method:'POST', body: fd });
          const data = await res.json();
          if (res.ok && data.status==='success' && data.transaction && data.transaction.stid){
            window.open(`/staff/transaction/certificate/${encodeURIComponent(data.transaction.stid)}?action=view`,'_blank');
            showDashboardMsgModal("Deposit successful!", "success");
          } else {
            showDashboardMsgModal(data.message || "Deposit failed.", "error");
          }
        }catch{ showDashboardMsgModal("Network error.", "error"); }
        depositBtn.disabled = false;
        depositBtn.innerHTML = origHTML;
      });
    }
    const withdrawBtn = document.getElementById('withdrawBtn');
    if (withdrawBtn){
      withdrawBtn.addEventListener('click', async ()=>{
        const w = formValues('withdraw');
        const requiredFields = Object.assign({}, w);
        delete requiredFields.remarks;
        if (Object.values(requiredFields).some(v => v==='' ) || !w.date){
          showDashboardMsgModal("Please fill all Withdraw fields.", "error");
          return;
        }
        w.type='withdraw';
        // --- Spinner animation ---
        const origHTML = withdrawBtn.innerHTML;
        withdrawBtn.disabled = true;
        withdrawBtn.innerHTML = `<span class="inline-flex items-center gap-2"><svg class="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>Processing...</span>`;
        try{
          const fd = new FormData();
          Object.entries(w).forEach(([k,v])=> fd.append(k,v));
          const res = await fetch('/staff/api/add-transaction',{ method:'POST', body: fd });
          const data = await res.json();
          if (res.ok && data.status==='success' && data.transaction && data.transaction.stid){
            window.open(`/staff/transaction/certificate/${encodeURIComponent(data.transaction.stid)}?action=view`,'_blank');
            showDashboardMsgModal("Withdrawal successful!", "success");
          } else {
            showDashboardMsgModal(data.message || "Withdrawal failed.", "error");
          }
        }catch{ showDashboardMsgModal("Network error.", "error"); }
        withdrawBtn.disabled = false;
        withdrawBtn.innerHTML = origHTML;
      });
    }
  });

  /* ================= Civil Score Floating Box (Fallback & Main) ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    // Initialize shared floating boxes if the external script loaded
    if (typeof initializeFloatingBoxes === 'function') {
      initializeFloatingBoxes();
    }
    
    // Fallback: ensure Civil Score floating button works even if shared.js failed to load
    const civilBtnEl = document.getElementById('civilBtn');
    const civilBoxEl = document.getElementById('civilBox');
    const closeCivilEl = document.getElementById('closeCivil');
    
    // Ensure the box is hidden initially
    if (civilBoxEl) {
      civilBoxEl.classList.add('hidden');
      civilBoxEl.classList.remove('show');
    }
    
    if (civilBtnEl && civilBoxEl && !civilBtnEl.dataset.wired) {
      civilBtnEl.addEventListener('click', () => {
        civilBoxEl.classList.toggle('hidden');
        if (!civilBoxEl.classList.contains('hidden')) {
          setTimeout(() => civilBoxEl.classList.add('show'), 10);
        } else {
          civilBoxEl.classList.remove('show');
        }
      });
      civilBtnEl.dataset.wired = '1';
    }
    
    if (closeCivilEl && civilBoxEl && !closeCivilEl.dataset.wired) {
      closeCivilEl.addEventListener('click', () => {
        civilBoxEl.classList.remove('show');
        setTimeout(() => civilBoxEl.classList.add('hidden'), 400);
      });
      closeCivilEl.dataset.wired = '1';
    }

    const checkCivilBtn = document.getElementById('checkCivil');
    const civilInput = document.getElementById('civilInput');
    const civilResult = document.getElementById('civilResult');
    function wireCivil(btn){
      if (!btn || btn.dataset.wired) return;
      btn.addEventListener('click', async ()=>{
        const val = civilInput.value.trim();
        civilResult.textContent = '';
        if (!val){
          civilResult.textContent = "Please enter Customer ID or KGID.";
          civilResult.className = "mt-3 text-center text-red-600";
          return;
        }
        civilResult.textContent = "Checking...";
        civilResult.className = "mt-3 text-center text-blue-700";
        try{
          const res = await fetch(`/api/check-civil-score?customer_id=${encodeURIComponent(val)}`);
          const data = await res.json();
          if (res.ok && data.status === "success"){
            const overall = (data.score || data.score===0) ? data.score : 'Unknown';
            civilResult.textContent = `Civil Score for ${val}: ${overall}`;
            civilResult.className = "mt-3 text-center text-green-700 font-bold";
          } else {
            civilResult.textContent = data.message || "Not found.";
            civilResult.className = "mt-3 text-center text-red-600";
          }
        }catch{
          civilResult.textContent = "Network error.";
          civilResult.className = "mt-3 text-center text-red-600";
        }
      });
      btn.dataset.wired='1';
    }
    wireCivil(checkCivilBtn);
  });

  /* ================= Loan Info Search (Staff) ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const form = document.getElementById('loanInfoSearchForm');
    const input = document.getElementById('loanInfoSearchInput');
    const result = document.getElementById('loanInfoSearchResult');
    if (!form || !input || !result) return;
    form.addEventListener('submit', async e=>{
      e.preventDefault();
      const val = (input.value||'').trim();
      result.innerHTML = '';
      if (!val){
        result.innerHTML = '<div class="text-red-600">Please enter a Loan ID.</div>';
        return;
      }
      result.innerHTML = '<div class="text-blue-600">Searching...</div>';
      const url = '/admin/api/loan-info?loan_id=' + encodeURIComponent(val);
      try{
        const res = await fetch(url);
        let data=null; try{ data = await res.json(); }catch{}
        if (res.ok && data && data.status==='success' && data.loan_info){
          const info = data.loan_info;
          result.innerHTML = `
            <div class="bg-gray-50 p-4 rounded shadow">
              <div><strong>Name:</strong> ${info.name ?? '-'} </div>
              <div><strong>Loan Amount:</strong> ₹${info.loan_amount ?? '-'} </div>
              <div><strong>Loan Term (months):</strong> ${info.loan_term_months ?? '-'} </div>
              <div><strong>Interest Rate:</strong> ${info.interest_rate ?? '-'}% </div>
              <div><strong>Next Installment Amount:</strong> ₹${info.next_installment_amount ?? '-'} </div>
              <div><strong>Outstanding Amount:</strong> ₹${info.outstanding_amount ?? '-'} </div>
            </div>`;
        } else {
          const msg = (data && data.message) ? data.message : 'No loan found.';
          result.innerHTML = `<div class="text-red-600">${msg}</div>`;
        }
      }catch{
        result.innerHTML = '<div class="text-red-600">Network error.</div>';
      }
    });
  });

  /* ================= Loan Repayment Search ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const loanSearchForm = document.getElementById('loanSearchForm');
    const loanSearchInput = document.getElementById('loanSearchInput');
    const loanSearchType = document.getElementById('loanSearchType');
    const loanInfoResult = document.getElementById('loanInfoResult');
    const autoTransactionFormContainer = document.getElementById('autoTransactionFormContainer');
    const loanRepaymentSection = document.getElementById('loanRepayment');
    if (!loanSearchForm) return;
    loanSearchForm.addEventListener('submit', async e=>{
      e.preventDefault();
      document.querySelectorAll('.dynamic-section').forEach(sec=>sec.classList.add('hidden'));
      loanRepaymentSection.classList.remove('hidden');
      loanInfoResult.innerHTML = '<div class="text-blue-600">Loading...</div>';
      autoTransactionFormContainer.innerHTML='';
      const searchVal = loanSearchInput.value.trim();
      const searchBy = loanSearchType.value;
      if (!searchVal){
        loanInfoResult.innerHTML = '<div class="text-red-600">Please enter a value.</div>';
        return;
      }
      try{
        let loanData=null;
        if (searchBy==='loanId'){
          const res = await fetch(`/finance/${encodeURIComponent(searchVal)}`);
          if (!res.ok) throw new Error('Loan not found');
          const data = await res.json();
          if (data && data.status==='success' && data.loan){
            loanData = data.loan;
          } else throw new Error(data.message || 'Loan not found');
        } else {
          const res = await fetch(`/finance/api/fetch_customer_details?customer_id=${encodeURIComponent(searchVal)}`);
          if (!res.ok) throw new Error('Customer not found');
          const data = await res.json();
            if (data && data.status==='success' && data.loans && data.loans.length>0){
            loanData = data.loans[0];
          } else throw new Error(data.message || 'No loans found');
        }
        loanInfoResult.innerHTML = `
          <div class="bg-gray-50 p-4 rounded shadow mb-4">
            <div><strong>Loan ID:</strong> ${loanData.loan_id || '-'}</div>
            <div><strong>Customer ID:</strong> ${loanData.customer_id || '-'}</div>
            <div><strong>Loan Type:</strong> ${loanData.loan_type || '-'}</div>
            <div><strong>Amount:</strong> ₹${Number(loanData.loan_amount||0).toLocaleString()}</div>
            <div><strong>Interest Rate:</strong> ${loanData.interest_rate || '-'}%</div>
            <div><strong>Term:</strong> ${loanData.loan_term_months || '-'} months</div>
            <div><strong>Status:</strong> ${loanData.status || '-'}</div>
          </div>`;
      }catch(err){
        loanInfoResult.innerHTML = `<div class="text-red-600">${err.message}</div>`;
      }
    });
  });

  /* ================= Recent Transactions (Staff) ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const ySel = document.getElementById('rtYearStaff');
    const mSel = document.getElementById('rtMonthStaff');
    const dSel = document.getElementById('rtDayStaff');
    const btn = document.getElementById('rtFilterBtnStaff');
    const body = document.getElementById('rtTableBodyStaff');
    function populateSelectors(){
      if (!ySel || !mSel || !dSel) return;
      const now = new Date();
      const cy = now.getFullYear();
      const cm = now.getMonth()+1;
      const cd = now.getDate();
      const years = [];
      for (let y=cy; y>=cy-5; y--) years.push(y);
      ySel.innerHTML = ['<option value="">All</option>'].concat(years.map(y=>`<option value="${y}">${y}</option>`)).join('');
      ySel.value = String(cy);
      const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      mSel.innerHTML = ['<option value="">All</option>'].concat(monthNames.map((n,i)=>`<option value="${i+1}">${n}</option>`)).join('');
      mSel.value = String(cm);
      const days = Array.from({length:31},(_,i)=>i+1);
      dSel.innerHTML = ['<option value="">All</option>'].concat(days.map(d=>`<option value="${d}">${d}</option>`)).join('');
      dSel.value = String(cd);
    }
    async function loadRecent(){
      if (!body) return;
      body.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-gray-500">Loading...</td></tr>';
      try{
        const qs = new URLSearchParams();
        if (ySel && ySel.value) qs.set('year', ySel.value);
        if (mSel && mSel.value) qs.set('month', mSel.value);
        if (dSel && dSel.value) qs.set('day', dSel.value);
        const res = await fetch(`/admin/api/recent-transactions${qs.toString()?('?'+qs.toString()):''}`);
        const data = await res.json();
        if (!res.ok || data.status!=='success') throw new Error(data.message || 'Failed to load');
        const events = data.events || [];
        if (!events.length){
          body.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-gray-500">No data</td></tr>';
          return;
        }
        body.innerHTML = events.map(ev=>`
          <tr>
            <td class="px-4 py-2">${ev.date ? new Date(ev.date).toLocaleString() : '-'}</td>
            <td class="px-4 py-2">${ev.type || '-'}</td>
            <td class="px-4 py-2">₹${Number(ev.amount||0).toLocaleString()}</td>
            <td class="px-4 py-2">${ev.details || '-'}</td>
            <td class="px-4 py-2">${ev.ref_id || '-'}</td>
          </tr>`).join('');
      }catch(e){
        body.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-red-600">Failed to load</td></tr>';
      }
    }
    populateSelectors();
    if (btn) btn.addEventListener('click', loadRecent);
    const navBtn = document.querySelector('.nav-button[data-target="recentTransactionsStaff"]');
    if (navBtn) navBtn.addEventListener('click', loadRecent);
  });

  /* ================= Queries (Staff View) ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const queriesTbody = document.getElementById('queriesTbody');
    const queriesMsg = document.getElementById('queriesMsg');
    const queriesNavBtn = document.querySelector('[data-target="queriesSection"]');
    async function fetchQueries(){
      if (!queriesTbody) return;
      queriesMsg.textContent='';
      queriesTbody.innerHTML='<tr><td colspan="8" class="px-4 py-2">Loading...</td></tr>';
      try{
        const res = await fetch('/api/queries');
        if (!res.ok) throw new Error('Network error');
        const payload = await res.json();
        if (payload.status!=='success') throw new Error(payload.message || 'Failed to load');
        renderQueries(payload.data || []);
      }catch(err){
        queriesTbody.innerHTML='<tr><td colspan="8" class="px-4 py-2 text-red-600">Error loading queries.</td></tr>';
        queriesMsg.textContent = err.message || String(err);
        queriesMsg.className='text-red-600';
      }
    }
    function renderQueries(list){
      if (!queriesTbody) return;
      if (!Array.isArray(list) || list.length===0){
        queriesTbody.innerHTML='<tr><td colspan="8" class="px-4 py-2">No queries found.</td></tr>';
        return;
      }
      const rows = list.map((q,idx)=>{
        const id = q.id || '';
        const name = q.name || '';
        const email = q.email || '';
        const phone = q.phone || '';
        const ident = q.kgid || q.customer_id || '';
        const desc = (q.description||'').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        const status = q.status || 'open';
        const created = q.created_at ? new Date(q.created_at).toLocaleString() : '';
        const actionBtn = status==='solved'
          ? `<button class="px-3 py-1 bg-gray-300 text-gray-700 rounded" disabled>Solved</button>`
          : `<button data-id="${id}" class="markSolvedBtn px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700">Mark Solved</button>`;
        return `
          <tr class="border-t">
            <td class="px-4 py-2 align-top">${idx+1}</td>
            <td class="px-4 py-2 align-top">${name}</td>
            <td class="px-4 py-2 align-top">${email}</td>
            <td class="px-4 py-2 align-top">${phone}</td>
            <td class="px-4 py-2 align-top">${ident}</td>
            <td class="px-4 py-2 align-top"><div title="${created}">${desc}</div></td>
            <td class="px-4 py-2 align-top">${status}</td>
            <td class="px-4 py-2 align-top">${actionBtn}</td>
          </tr>`;
      }).join('\n');
      queriesTbody.innerHTML = rows;
      document.querySelectorAll('.markSolvedBtn').forEach(btn=>{
        if (btn.dataset.wired) return;
        btn.addEventListener('click', async ()=>{
          const id = btn.getAttribute('data-id');
          if (!id) return;
          btn.disabled = true; btn.textContent = 'Marking...';
          try{
            const res = await fetch(`/api/queries/${id}/mark-solved`, { method:'POST' });
            const data = await res.json();
            if (res.ok && data.status==='success'){
              fetchQueries();
            } else {
              alert(data.message || 'Failed to mark solved');
              btn.disabled=false; btn.textContent='Mark Solved';
            }
          }catch{
            alert('Network error');
            btn.disabled=false; btn.textContent='Mark Solved';
          }
        });
        btn.dataset.wired='1';
      });
    }
    if (queriesNavBtn){
      queriesNavBtn.addEventListener('click', ()=> setTimeout(fetchQueries,150));
    }
    fetchQueries();
  });

  /* ================= Next Installment Lookup ================= */
  document.addEventListener('DOMContentLoaded', ()=>{
    const nextInstallmentSection = document.getElementById('nextInstallment');
    if (!nextInstallmentSection) return;
    const searchBtn = document.getElementById('nextInstallmentSearchBtn');
    const searchInput = document.getElementById('nextInstallmentAccount');
    const loanAmountEl = document.getElementById('loanAmount');
    const paidAmountEl = document.getElementById('paidAmount');
    const remainingAmountEl = document.getElementById('remainingAmount');
    const nextMonthAmountEl = document.getElementById('nextMonthAmount');
    if (searchBtn){
      searchBtn.addEventListener('click', async ()=>{
        nextInstallmentSection.querySelector('.error-msg')?.remove();
        const account = searchInput.value.trim();
        if (!account){
          const err = document.createElement('div');
          err.className='error-msg text-red-600 mb-2';
          err.textContent='Please enter a valid account number.';
          nextInstallmentSection.prepend(err);
          loanAmountEl.textContent = paidAmountEl.textContent = remainingAmountEl.textContent = nextMonthAmountEl.textContent = '-';
          return;
        }
        loanAmountEl.textContent = paidAmountEl.textContent = remainingAmountEl.textContent = nextMonthAmountEl.textContent = 'Loading...';
        try{
          const tryUrls = [
            `/api/next-installment?account=${encodeURIComponent(account)}`,
            `/loan/api/next-installment?loan_id=${encodeURIComponent(account)}`
          ];
          let data=null;
          for (const url of tryUrls){
            try{
              const res = await fetch(url);
              if (!res.ok) continue;
              data = await res.json();
              break;
            }catch{}
          }
          if (!data) throw new Error('Failed to fetch');
          const loanIdentifierEl = document.getElementById('loanIdentifier');
          if (loanIdentifierEl) loanIdentifierEl.textContent = data.loan_id || data.customer_id || data.account || '-';
          loanAmountEl.textContent = data.loanAmount ? `₹${Number(data.loanAmount).toLocaleString()}` : '-';
          paidAmountEl.textContent = data.paidAmount ? `₹${Number(data.paidAmount).toLocaleString()}` : '-';
          remainingAmountEl.textContent = data.remainingAmount ? `₹${Number(data.remainingAmount).toLocaleString()}` : '-';
          nextMonthAmountEl.textContent = data.nextMonthAmount ? `₹${Number(data.nextMonthAmount).toLocaleString()}` : '-';
        }catch{
          const e = document.createElement('div');
          e.className='error-msg text-red-600 mb-2';
          e.textContent='Error fetching installment details.';
          nextInstallmentSection.prepend(e);
          loanAmountEl.textContent = paidAmountEl.textContent = remainingAmountEl.textContent = nextMonthAmountEl.textContent = '-';
        }
      });
    }
  });

})();
