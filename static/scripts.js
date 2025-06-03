// static/scripts.js

document.addEventListener('DOMContentLoaded', ()=>{

  // Robust postJSON: JSON.parse fallback to text
  async function postJSON(url,data){
    let res = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data||{})
    });
    let txt = await res.text();
    try { return JSON.parse(txt); }
    catch { return {message: txt}; }
  }

  // Camera setup
  const video = document.getElementById('video');
  video.style.display = 'none';  // hide until needed
  if (video) {
    navigator.mediaDevices.getUserMedia({video:true})
      .then(stream => video.srcObject = stream)
      .catch(console.error);
  }

  // ── Registration Flow ──────────────────────────────────────────
  if (document.getElementById('scan-rfid-reg')) {
    let regRFID = null, faceOK = false;
    const rollI    = document.getElementById('roll'),
          nameI    = document.getElementById('name'),
          emailI   = document.getElementById('email'),
          bRF      = document.getElementById('scan-rfid-reg'),
          bFace    = document.getElementById('capture-face'),
          bSub     = document.getElementById('submit'),
          sRF      = document.getElementById('rfid-status'),
          sFace    = document.getElementById('face-status'),
          resR     = document.getElementById('result'),
          rollErr  = document.getElementById('roll-error'),
          nameErr  = document.getElementById('name-error'),
          emailErr = document.getElementById('email-error');

    // Enable Scan-RFID only when fields are non-empty AND valid
    function toggleRF() {
      const ok = rollI.value.trim() &&
                 nameI.value.trim() &&
                 emailI.value.trim() &&
                 rollI.checkValidity() &&
                 nameI.checkValidity() &&
                 emailI.checkValidity();
      bRF.disabled = !ok;
    }

    // Show or clear error messages on input
    rollI.addEventListener('input', () => {
      rollErr.textContent = rollI.checkValidity() ? '' : rollI.title;
      toggleRF();
    });
    nameI.addEventListener('input', () => {
      nameErr.textContent = nameI.checkValidity() ? '' : nameI.title;
      toggleRF();
    });
    emailI.addEventListener('input', () => {
      emailErr.textContent = emailI.checkValidity()
        ? ''
        : (emailI.validity.valueMissing
            ? 'Email is required'
            : 'Enter a valid email address');
      toggleRF();
    });

    toggleRF();
    bFace.disabled = true;
    bSub.disabled  = true;

    // RFID scan with 10s countdown
    bRF.addEventListener('click', ()=>{
      let remaining = 10;
      sRF.textContent = `Waiting for card (${remaining}s)…`;
      bRF.disabled = true;
      bFace.disabled = true;

      const timer = setInterval(()=>{
        remaining--;
        if (remaining >= 0) {
          sRF.textContent = `Waiting for card (${remaining}s)…`;
        }
      }, 1000);

      postJSON('/scan_rfid', {})
        .then(r => {
          clearInterval(timer);
          regRFID = r.rfid || null;
          sRF.textContent = r.message;
          bFace.disabled = !regRFID;
        })
        .catch(() => {
          clearInterval(timer);
          sRF.textContent = "Error";
        })
        .finally(() => {
          clearInterval(timer);
          bRF.disabled = false;
        });
    });

    // Face capture
    bFace.addEventListener('click', ()=>{
      if (!regRFID) return;
      video.style.display = 'block';
      const c = document.createElement('canvas');
      c.width  = video.videoWidth;
      c.height = video.videoHeight;
      c.getContext('2d').drawImage(video, 0, 0);

      postJSON('/capture_face', {
        rfid:  regRFID,
        image: c.toDataURL('image/jpeg')
      })
      .then(r => {
        sFace.textContent = r.message;
        if (r.message === "Face captured") {
          faceOK = true;
          bSub.disabled = false;
        }
      })
      .catch(() => {
        sFace.textContent = "Error";
      })
      .finally(() => {
        video.style.display = 'none';
      });
    });

    // Final registration submit
    bSub.addEventListener('click', ()=>{
      postJSON('/register_student',{
        rfid:  regRFID,
        roll:  rollI.value.trim(),
        name:  nameI.value.trim(),
        email: emailI.value.trim()
      })
      .then(r => {
        resR.textContent = r.message;
    
        // After 5 seconds: clear form + messages + UI
        setTimeout(() => {
          resR.textContent = '';
          sRF.textContent   = '';
          sFace.textContent = '';
          rollI.value  = '';
          nameI.value  = '';
          emailI.value = '';
          rollErr.textContent  = '';
          nameErr.textContent  = '';
          emailErr.textContent = '';
          regRFID = null;
          faceOK  = false;
          bFace.disabled = true;
          bSub.disabled  = true;
          toggleRF();
        }, 5000);
      })
      .catch(()=>{
        resR.textContent = "Error";
      });
    });
    
  }

  // ── Attendance Flow ────────────────────────────────────────────
  if (document.getElementById('scan-rfid')) {
    let pending = null;
    const bRF   = document.getElementById('scan-rfid'),
          bFace = document.getElementById('scan-face'),
          msg   = document.getElementById('message');

    bFace.disabled = true;

    // RFID scan with 10s countdown
    bRF.addEventListener('click', ()=>{
      let remaining = 10;
      msg.textContent = `Waiting for card (${remaining}s)…`;
      bRF.disabled = true;
      bFace.disabled = true;

      const timer = setInterval(()=>{
        remaining--;
        if (remaining >= 0) {
          msg.textContent = `Waiting for card (${remaining}s)…`;
        }
      }, 1000);

      postJSON('/scan_rfid', {})
        .then(r => {
          clearInterval(timer);
          pending = r.rfid || null;
          msg.textContent = r.message;
          if (!pending) {
            setTimeout(()=> msg.textContent = '', 2000);
          } else {
            bFace.disabled = false;
          }
        })
        .catch(() => {
          clearInterval(timer);
          msg.textContent = "Error";
          setTimeout(()=> msg.textContent = '', 2000);
        })
        .finally(() => {
          clearInterval(timer);
          bRF.disabled = false;
        });
    });

    // Face & RFID verification
    bFace.addEventListener('click', ()=>{
      if (!pending) {
        msg.textContent = "Scan RFID first";
        setTimeout(()=> msg.textContent = '', 2000);
        return;
      }
      video.style.display = 'block';
      const c = document.createElement('canvas');
      c.width  = video.videoWidth;
      c.height = video.videoHeight;
      c.getContext('2d').drawImage(video, 0, 0);

      postJSON('/verify_both', {
        rfid:  pending,
        image: c.toDataURL('image/jpeg')
      })
      .then(r => {
        if (r.roll && r.message.includes("Marked Present")) {
          msg.innerHTML = `<strong>${r.message}</strong><br>
            Roll: ${r.roll}<br>
            Name: ${r.name}<br>
            Email: ${r.email}<br>
            Time: ${r.time}`;
        } else {
          msg.textContent = r.message;
        }
        setTimeout(()=> msg.textContent = '', 3000);
      })
      .catch(() => {
        msg.textContent = "Error";
        setTimeout(()=> msg.textContent = '', 2000);
      })
      .finally(() => {
        video.style.display = 'none';
        pending = null;
        bFace.disabled = true;
      });
    });
  }

});
