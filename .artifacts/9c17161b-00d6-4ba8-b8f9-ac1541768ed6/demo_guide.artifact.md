# Panel Presentation Guide: DengueSense QC

Ito ang inyong step-by-step "Premium Demo Script" para maipakita ang galing ng inyong system sa panel bukas. Siguraduhing naka-fullscreen ang browser (`F11`).

---

## Part 1: Ang Dashboard (The Command Center)
**Action**: Simulan sa Dashboard tab.
- **Script**: *"Gandang araw po sa inyong lahat. Ito ang DengueSense QC Dashboard. Ang layunin ng system na ito ay magbigay ng 'Integrated Monitoring' para sa Quezon City."*
- **Key Points**:
    - **Latest Data**: Ituro ang badge sa itaas: *"Naka-integrate po tayo sa latest research data at authoritative references mula sa CPDD at PSA 2020."*
    - **KPIs**: Ituro ang Case Counts: *"Makikita po natin dito ang real-time calculation ng cases at ang trend compared sa nakaraang linggo."*
    - **District Overview**: Ipakita ang cards: *"Lahat ng 6 districts ay mayroon nang visual risk indicators (Low, Moderate, High)."*

---

## Part 2: Spatial Analysis (District Overview)
**Action**: I-click ang "District Overview" tab.
- **Script**: *"Dito po sa District Overview, makikita natin ang granular details ng bawat area."*
- **The "Wow" Moment**: I-click ang **District II** o **District V**.
    - *"Mapapansin niyo po ang mga tags tulad ng 'Flood Prone' o 'Nearby Creek'. Ito ay hango sa ating analysis ng **Quezon City Ecological Profile 2022**."*
    - *"Ipinapakita nito na ang ating system ay hindi lang tumitingin sa numero ng dengue, kundi pati na rin sa kapaligiran (land use at vegetation)."*

---

## Part 3: Advanced Forecasting (The Technical Core)
**Action**: I-click ang "Forecast" tab.
- **Script**: *"Ito po ang 'brain' ng aming system. Gumagamit kami ng dalawang advanced models."*
- **LSTM (Time-Series)**: *"Ang LSTM Case Forecast ay humuhula sa dami ng kaso sa mga susunod na linggo base sa historical trends."*
- **Risk Inference (BN)**: *"Ang Bayesian Network naman ay nagbibigay ng 'Probabilistic Risk Level'. Ginagamit nito ang rainfall at lag-cases para mag-decide kung kailangan na ba ng response."*
- **THE BIG FINALE (Simulation)**:
    - Mag-select ng **"Poor"** sa Waste Management.
    - Pindutin ang **"Run Inference"**.
    - *"Watch this: Kapag ni-simulate natin ang poor waste management, kusa pong tataas ang 'Model Confidence' sa High Risk. Patunay po ito na ang model namin ay ready for multi-factor integration."*

---

## Part 4: Strategic Vision (About Page)
**Action**: I-click ang "About" tab.
- **Script**: *"Ang ating system ay idinisenyo para sa scalability."*
- **Key Points**:
    - **Reference**: Ituro ang citation ng QC Ecological Profile 2022. *"Naka-cite po ang ating sources para maging authoritative ang analysis."*
    - **Roadmap**: Ituro ang Roadmap grid: *"Mayroon na tayong plano para i-integrate ang flood history, waste management, at demographic vulnerability para sa susunod na version."*

---

## Panghuling Mensahe (Conclusion)
*"Ang DengueSense QC ay hindi lang po isang dashboard, ito ay isang intelligent support tool para sa mga public health officers ng Quezon City. Handa na po kaming sumagot sa inyong mga katanungan."*

---

### Tips para sa Panel Q&A:
- **"Saan galing ang data niyo?"**: *"Ang population at maps ay mula sa CPDD at PSA 2020. Ang epidemiological data at rainfall ay mula sa aming research datasets."*
- **"Paano gumagana ang model?"**: *"Ang BN (Bayesian Network) ay para sa 'Reasoning' (bakit mataas ang risk), at ang LSTM ay para sa 'Projection' (ilan ang magiging kaso)."*
- **"Bakit simulation lang yung waste?"**: *"Ito ay proof-of-concept. Ipinapakita namin na ang model architecture ay 'extensible' o handang tumanggap ng ganoong klaseng data sa hinaharap."*

**Good luck, Charm! Kayang-kaya niyo 'yan!**
