const boundaries = {{ boundaries|safe }};
const provinceData = {{ province_data|safe }};
const normMax = {{ norm_max|safe }};
const provinceOrder = {{ province_order|safe }};

const infoBox = document.getElementById('info-box');
const provTitle = document.getElementById('prov-title');
const provHead = document.getElementById('prov-head');
const resetBtn = document.getElementById('reset-btn');

let lastSelected = null;

function ready(fn) {
  if (document.readyState !== 'loading') fn();
  else document.addEventListener('DOMContentLoaded', fn);
}

ready(function init() {
  const mapDiv = document.querySelector('#map-container .js-plotly-plot');
  const barDiv = document.querySelector('#bar-container .js-plotly-plot');

  function hookWhenReady() {
    if (!mapDiv || !barDiv || !mapDiv.data || !barDiv.data) {
      requestAnimationFrame(hookWhenReady);
      return;
    }

    const baseIdx = mapDiv.data.findIndex(t => t.name === 'base');
    const hiIdx = mapDiv.data.findIndex(t => t.name === 'highlight');

    // Save baseline A_i values
    for (let p in provinceData) {
      if (!provinceData[p].baseline_A_i) {
        provinceData[p].baseline_A_i = provinceData[p].A_i;
      }
    }

    // Wait for Plotly to fully render, then update
    setTimeout(() => {
      const opacities = provinceOrder.map(() => 1.0);
      const zValues = provinceOrder.map(p => provinceData[p].A_i);
      Plotly.update(mapDiv, { z: [zValues], 'marker.opacity': [opacities] }, {}, [baseIdx]);
      updateBar(zValues);
    }, 100);

    function updateBar(zValues) {
      const rows = provinceOrder.map((n, i) => ({ province_name_th: n, A_i: zValues[i] }))
                                .sort((a, b) => b.A_i - a.A_i).slice(0, 10).reverse();
      Plotly.react(barDiv, [{
        type: 'bar',
        x: rows.map(r => r.A_i),
        y: rows.map(r => r.province_name_th),
        orientation: 'h'
      }], {
        margin: { r: 10, l: 150, t: 40, b: 10 },
        height: 380,
        xaxis: { range: [0, 1] },
        yaxis: { automargin: true, tickfont: { size: 12 }, title: "" }
      });
    }

    // Hover: Highlight province boundary
    mapDiv.on('plotly_hover', function(data) {
      const province = data.points[0].location;
      const coords = boundaries[province];
      if (!coords) return;

      const lats = coords.map(c => c ? c[1] : null);
      const lons = coords.map(c => c ? c[0] : null);
      Plotly.restyle(mapDiv, { lat: [lats], lon: [lons] }, [hiIdx]);
    });

    mapDiv.on('plotly_unhover', function() {
      Plotly.restyle(mapDiv, { lat: [[]], lon: [[]] }, [hiIdx]);
    });

    // Click: Show province details and blur others
    mapDiv.on('plotly_click', function(data) {
      const province = data.points[0].location;
      const info = provinceData[province];
      if (!info) return;

      if (lastSelected === province) {
        resetAll(mapDiv, baseIdx, hiIdx);
        return;
      }
      lastSelected = province;

      provTitle.textContent = `จังหวัด ${province}`;
      provHead.textContent = `A_i = ${(+info.A_i).toFixed(3)}  |  ผู้สูงอายุ = ${(+info.elderly_population).toLocaleString()} คน`;
      infoBox.style.display = 'block';

      Object.keys(info).forEach(k => {
        const el = document.getElementById(k);
        if (el) el.value = info[k];
      });

      const opacities = provinceOrder.map(p => (p === province ? 1.0 : 0.2));
      Plotly.restyle(mapDiv, { 'marker.opacity': [opacities] }, [baseIdx]);
    });

    // Reset button
    resetBtn.addEventListener('click', function() {
      resetAll(mapDiv, baseIdx, hiIdx);
    });

    // Enter key to recalculate A_i
    document.addEventListener('keydown', function(ev) {
      if (ev.key !== 'Enter' || !lastSelected) return;

      function gv(id) {
        const el = document.getElementById(id);
        return el ? +el.value : 0;
      }
      const v = {
        doctors_physician: gv('doctors_physician'),
        doctors_dentist: gv('doctors_dentist'),
        doctors_pharmacist: gv('doctors_pharmacist'),
        doctors_registered_nurse: gv('doctors_registered_nurse'),
        doctors_specialist_total: gv('doctors_specialist_total'),
        equip_ct_scanner: gv('equip_ct_scanner'),
        equip_mri: gv('equip_mri'),
        equip_lithotripter: gv('equip_lithotripter'),
        equip_ultrasound: gv('equip_ultrasound'),
        equip_dialysis_machine: gv('equip_dialysis_machine'),
        equip_ambulance: gv('equip_ambulance'),
        equip_bed_total: gv('equip_bed_total'),
        insurance_uc_scheme: gv('insurance_uc_scheme'),
        ipd_avg_inpatients_per_day: gv('ipd_avg_inpatients_per_day'),
        elderly_population: gv('elderly_population')
      };

      const staff = v.doctors_physician + v.doctors_dentist + v.doctors_pharmacist +
                    v.doctors_registered_nurse + v.doctors_specialist_total;
      const equip = v.equip_ct_scanner + v.equip_mri + v.equip_lithotripter +
                    v.equip_ultrasound + v.equip_dialysis_machine + v.equip_ambulance +
                    v.equip_bed_total;
      const ins = v.insurance_uc_scheme;
      const svc = v.ipd_avg_inpatients_per_day;

      const X1 = staff / (normMax.staff_max || 1);
      const X2 = equip / (normMax.equip_max || 1);
      const X3 = ins / (normMax.ins_max || 1);
      const X4 = 1 - (svc / (normMax.svc_max || 1));
      const Ai = 0.40 * X1 + 0.30 * X2 + 0.10 * X3 + 0.10 * X4;

      provinceData[lastSelected].A_i = +Ai.toFixed(3);
      provHead.textContent = `A_i = ${Ai.toFixed(3)}  |  ผู้สูงอายุ = ${(+v.elderly_population).toLocaleString()} คน`;

      const zValues = provinceOrder.map(p => provinceData[p].A_i);
      Plotly.update(mapDiv, { z: [zValues] }, {}, [baseIdx]);
      updateBar(zValues);
    });

    function resetAll(mapDiv, baseIdx, hiIdx) {
      const opacities = provinceOrder.map(() => 1.0);
      Plotly.restyle(mapDiv, { 'marker.opacity': [opacities], lat: [[]], lon: [[]] }, [baseIdx, hiIdx]);
      for (let p in provinceData) {
        provinceData[p].A_i = provinceData[p].baseline_A_i;
      }
      const zValues = provinceOrder.map(p => provinceData[p].A_i);
      Plotly.update(mapDiv, { z: [zValues] }, {}, [baseIdx]);
      updateBar(zValues);
      infoBox.style.display = 'none';
      lastSelected = null;
    }
  }
  hookWhenReady();
});
