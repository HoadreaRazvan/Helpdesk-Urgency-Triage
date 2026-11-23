# P2 — Responsible Service Triage Model: explicație detaliată

> Explicație în limba română a prezentării **„P2 — Responsible Service Triage Model.pptx”**
> (Basics of Artificial Intelligence · Proiectul 2 din 4).

## Despre proiect

| | |
|---|---|
| **Curs** | Basics of Artificial Intelligence |
| **Proiect** | 2 din 4: primul proiect de **învățare supervizată** (după P1, planificarea de rute) |
| **Laboratoare** | L5–L8 |
| **Pondere** | 20% din notă |
| **Echipă** | Aceeași echipă de 5 persoane |
| **Scopul** | Un semnal consultativ **„urgent review”** pentru tichetele unui help desk |

Ideea principală: **nu contează scorul cel mai mare, ci o evaluare onestă și responsabilă**, în care un client real ar putea avea încredere.

---

## 1. Problema, pe înțelesul tuturor

Gândește-te la **triajul de la Urgențe**. Pacienții vin unul după altul, iar o asistentă decide cine intră primul la medic, în funcție de cât de grav arată fiecare caz.

În proiect, „pacienții” sunt **tichetele** trimise la un **help desk**, adică un serviciu de suport tehnic. Oamenii scriu acolo „nu-mi merge contul”, „a căzut internetul în sală”, „vreau să-mi schimb parola” etc. Zilnic vin foarte multe, iar **unele urgente se pierd printre cele banale**.

Clientul vrea un program care, la fiecare tichet nou, să spună: *„Acesta pare urgent, uitați-vă întâi la el.”*

Fluxul dorit (slide 2):
1. **Sosește un tichet nou**, cu categorie, canal, lungimea descrierii și ora trimiterii.
2. **Modelul sugerează „urgent review”**, adică doar un semnal pentru personal.
3. **Personalul decide.** Semnalul schimbă doar ordinea în care se uită la tichete.

Programul **doar sugerează**. Nu închide tichete și nu refuză pe nimeni. Un om ia decizia finală. De aici vine „**Responsible**” din titlu: modelul trebuie folosit într-un mod care nu face rău nimănui.

### Cele patru reguli obligatorii (slide 3)

| # | Regula | Ce înseamnă |
|---|---|---|
| 01 | **Doar consultativ** | Modelul recomandă, nu refuză automat nicio cerere. |
| 02 | **Doar informații disponibile la trimitere** | Fără timp de rezolvare sau prioritate atribuită ulterior (vezi secțiunea 4, *data leakage*). |
| 03 | **Doar date aprobate** | CSV-ul sintetic dat de profesor sau un set public aprobat. Fără tichete reale, identificabile, ale universității. |
| 04 | **Setul de test se folosește o singură dată** | Se „îngheață” înainte de orice modelare și se rulează o singură dată, în L8, cu setările finale. |

---

## 2. Ce înseamnă „învățare supervizată”

Calculatorul nu știe singur ce e urgent. Îi dai **multe tichete vechi pentru care știi deja răspunsul** (urgent sau nu), iar el caută tipare, de exemplu: *„tichetele venite pe telefon, din categoria «rețea», sunt des urgente”*.

Apoi, pentru un tichet **nou**, la care nu știi răspunsul, aplică tiparele învățate și face o estimare.

„Supervizată” înseamnă că a învățat din exemple **cu răspunsul corect inclus**, ca un elev care învață din culegere cu soluții la final.

---

## 3. Datele (slide 4)

Datele sunt un tabel în care fiecare rând e un tichet. Un exemplu inventat:

| ticket_id | submitted_at | category | description_length | initial_channel | urgent_label |
|---|---|---|---|---|---|
| T001 | 02.03, 09:14 | parolă | 45 | email | 0 |
| T002 | 02.03, 09:20 | rețea | 310 | telefon | 1 |
| T003 | 02.03, 10:05 | software | 120 | formular web | 0 |

Ce rol are fiecare coloană:
- **`ticket_id`**: doar un număr de ordine. **Nu se dă modelului**, pentru că numărul tichetului nu are nicio legătură cu urgența.
- **`submitted_at`**: data și ora trimiterii. Se folosește pentru a ordona tichetele în timp.
- **`category`, `description_length`, `initial_channel`**: acestea sunt **feature-urile**, adică informațiile din care modelul învață.
- **`urgent_label`**: **ținta (target)**, răspunsul corect (1 = urgent, 0 = nu). Pe el încearcă modelul să-l ghicească.

Datele sunt **sintetice** (inventate de profesor), ca să nu folosiți tichete reale cu date personale.

Ce trebuie făcut **înainte de modelare**:
- verificați că fiecare feature exista la momentul trimiterii;
- notați proveniența datelor și ce utilizare e permisă;
- înghețați setul de test;
- dacă același solicitant apare de mai multe ori, grupați-i tichetele (vezi secțiunea 5);
- luați în calcul o împărțire pe timp (vezi secțiunea 5).

---

## 4. Regula cea mai importantă: fără „informații din viitor” (data leakage)

Să zicem că tabelul ar avea și coloana **`resolution_time`**, adică în cât timp s-a rezolvat tichetul.

Tichetele urgente au fost rezolvate repede, deci modelul ar învăța: *„rezolvat în mai puțin de o oră → urgent”*. Ar obține o acuratețe de 99% și ar părea genial.

**Problema:** când sosește un tichet nou, el **încă nu e rezolvat**, deci nu ai cum să știi cât va dura rezolvarea. Modelul ar fi inutil în realitate.

E ca un elev care ia 10 la un test pentru că avea răspunsurile scrise pe foaie. Nota arată bine, dar nu spune nimic despre ce știe de fapt.

De aceea regula spune: **dacă o informație nu exista în momentul trimiterii tichetului, nu ai voie s-o folosești.**

---

## 5. Împărțirea datelor: antrenare, validare, test

Datele se împart în **trei grupuri**. Cel mai ușor se înțelege prin analogia cu un examen:

| Grup | Analogie | La ce folosește |
|---|---|---|
| **Antrenare (train)** | Exercițiile din culegere, cu soluții | Modelul învață din ele |
| **Validare (validation)** | Simularea de examen | Compari modele și reglezi setări (de exemplu pragul, vezi secțiunea 9) |
| **Test** | **Examenul real** | Măsori o singură dată cât de bun e modelul final |

**De ce se folosește setul de test o singură dată?** Dacă te uiți la subiectele de examen, modifici ceva și te uiți din nou, ajungi să-ți potrivești răspunsurile pe acel examen. Nota obținută nu mai arată cât de bine te-ai descurca pe un examen nou. De aceea testul se „îngheață” la început și se deschide abia în L8.

**Două detalii importante:**
- **Împărțire în timp (time-based split):** antrenezi pe tichetele mai vechi (de exemplu ianuarie–septembrie) și testezi pe cele mai noi (octombrie–decembrie). Așa va fi folosit modelul și în realitate: învață din trecut și prezice viitorul.
- **Gruparea pe solicitant:** dacă aceeași persoană a trimis 5 tichete aproape identice, iar 3 ajung în antrenare și 2 în test, modelul o „recunoaște” și pare mai bun decât e. Toate tichetele unei persoane trebuie puse în același grup.

---

## 6. Baseline-uri: comparația cu soluții simple (slide 5)

Înainte de un model „inteligent”, construiești două soluții foarte simple, ca reper.

**Baseline 1, clasa majoritară.** Răspunde mereu „nu e urgent”. Dacă din 100 de tichete 80 nu sunt urgente, are o **acuratețe de 80%** fără să facă nimic, dar **nu prinde niciun tichet urgent**. Arată de ce acuratețea singură te poate păcăli.

**Baseline 2, o regulă scrisă de mână.** De exemplu: *„dacă categoria e «securitate» sau «server căzut», marchează urgent”*. E simplă și oricine o înțelege.

**Concluzia:** un model de machine learning **are sens doar dacă e mai bun decât aceste reguli simple.** Altfel, folosești regula, care e mai ieftină și mai transparentă.

---

## 7. Cele două modele (slide 5)

**Model A, regresia logistică.** Fiecare feature primește o „greutate”: de exemplu, *canal = telefon* adaugă puncte spre urgent, iar *categorie = parolă* scade puncte. Scorul total e transformat într-o **probabilitate între 0 și 1** (de exemplu 0,73, adică 73% șanse să fie urgent). Avantajul e că vezi exact de ce a decis modelul așa.

**Model B, ansamblul de arbori.** Un **arbore de decizie** e o serie de întrebări: *„A venit pe telefon? Da. Descrierea are peste 200 de caractere? Da. → urgent.”* Un **random forest** (sau **gradient boosting**) construiește sute de astfel de arbori, puțin diferiți între ei, care **votează** împreună. De obicei e mai precis, dar mai greu de explicat.

### Pipeline și cross-validation, explicate simplu

- Modelul lucrează doar cu numere, deci datele trebuie **pregătite**: categoriile (text) devin numere, iar valorile sunt aduse la aceeași scară. Asta e **preprocesarea**.
- **Cross-validation:** împarți datele de antrenare în 5 bucăți. Antrenezi pe 4 și verifici pe a 5-a, apoi repeți de 5 ori, schimbând bucata de verificare. Faci media rezultatelor, ca să nu depinzi de o singură împărțire „norocoasă”.
- Un **Pipeline** (din scikit-learn) leagă preprocesarea de model. Așa, la fiecare din cele 5 runde, preprocesarea învață **doar din cele 4 bucăți de antrenare**. Altfel bucata de verificare ar „scăpa” informații în ea: tot un fel de trișat.

---

## 8. Cum măsori cât de bun e modelul (slide 6)

### Matricea de confuzie: cele 4 situații posibile

| | Modelul zice „urgent” | Modelul zice „nu e urgent” |
|---|---|---|
| **E chiar urgent** | ✅ **TP**: prins corect | ❌ **FN**: **ratat** (omul așteaptă degeaba) |
| **Nu e urgent** | ⚠️ **FP**: **alarmă falsă** (personalul pierde puțin timp) | ✅ **TN**: corect ignorat |

### Exemplul din prezentare (100 de tichete)

Din cele 100 de tichete, 20 sunt cu adevărat urgente și 80 nu sunt.

| | Zice urgent | Zice nu |
|---|---|---|
| **Urgent (20)** | TP = **16** | FN = **4** |
| **Nu e urgent (80)** | FP = **12** | TN = **68** |

**Recall (sensibilitate): din tichetele urgente, câte am prins?**
16 prinse din 20 urgente = **0,80**, adică am prins 80% și am ratat 4.

**Precision: din câte ori am zis „urgent”, de câte ori am avut dreptate?**
Modelul a marcat 16 + 12 = 28 de tichete, dintre care 16 erau chiar urgente: 16 / 28 ≈ **0,57**. Deci 12 din cele 28 au fost alarme false.

**F1: o singură notă care combină recall și precision.**
F1 = 2 · 0,57 · 0,80 / (0,57 + 0,80) ≈ **0,67**

> Cifrele sunt un exemplu didactic din brief, nu performanța la care ar trebui să vă așteptați.

### De ce nu e suficientă acuratețea

- Acuratețea modelului: (16 + 68) / 100 = **84%**
- Acuratețea baseline-ului care zice mereu „nu”: **80%**

La prima vedere diferența pare mică (84% față de 80%). În realitate, modelul prinde **16 tichete urgente din 20**, iar baseline-ul **niciunul**. Acuratețea ascunde exact lucrul care contează pentru client.

### Calibrarea

Modelul dă probabilități. **Calibrarea** verifică dacă ele sunt „cinstite”: dacă modelul dă scorul 0,7 la 100 de tichete, aproximativ 70 dintre ele ar trebui să fie chiar urgente. Dacă doar 30 sunt, modelul e prea sigur pe el și personalul nu se poate baza pe scorurile lui.

---

## 9. Alegerea pragului (slide 7)

Modelul nu spune direct „da/nu”, ci dă o probabilitate (de exemplu 0,42). **Pragul** decide de la ce valoare tichetul e marcat urgent:
- cu pragul **0,5**: 0,42 → nu e marcat;
- cu pragul **0,3**: 0,42 → **e marcat**.

**Compromisul:**
- **Prag mai mic** → mai multe tichete marcate → **prinzi mai multe urgente**, dar ai **mai multe alarme false**.
- **Prag mai mare** → mai puține alarme false, dar **ratezi mai multe urgente**.

Cele două greșeli **nu costă la fel**. Un tichet urgent ratat (de exemplu un server căzut în sesiune) e mult mai grav decât o alarmă falsă, la care cineva pierde 2 minute.

**Exemplu cu cifre inventate.** Echipa decide că un tichet ratat costă **10 puncte**, iar o alarmă falsă **1 punct**. Apoi încearcă mai multe praguri pe setul de **validare**:

| Prag | Ratate (FN) | Alarme false (FP) | Cost total |
|---|---|---|---|
| 0,7 | 8 | 5 | 8·10 + 5·1 = **85** |
| 0,5 | 4 | 12 | 4·10 + 12·1 = **52** |
| 0,3 | 2 | 25 | 2·10 + 25·1 = **45** ← cel mai mic |

Se alege **0,3** și se „îngheață” înainte de L8.

Pașii, pe scurt:
1. Declarați explicit costul unui FN și al unui FP, justificat din perspectiva clientului.
2. Încercați mai multe praguri pe setul de validare.
3. Înghețați alegerea înainte de L8.

Ideea e că 0,5 e doar o valoare implicită: pragul trebuie ales pe baza costurilor, **pe validare, niciodată pe test.**

---

## 10. Ce faceți concret la fiecare laborator (slide 8)

| Lab | Pe scurt |
|---|---|
| **L5** | Vă uitați prin date, verificați că fiecare coloană exista la momentul trimiterii, împărțiți datele (inclusiv testul înghețat) și construiți cele 2 baseline-uri. |
| **L6** | Construiți pipeline-ul, antrenați regresia logistică și un ansamblu de arbori cu cross-validation și le comparați. |
| **L7** | Alegeți pragul pe validare, analizați **10 greșeli** ale modelului (de ce a greșit?), verificați calibrarea și vă gândiți la o **schimbare plauzibilă** (de exemplu apare un nou canal, cum ar fi un chat, sau în sesiune vin de 3 ori mai multe tichete). Modelul ar mai funcționa? |
| **L8** | Înghețați totul, rulați testul **o singură dată**, prezentați rezultatele (model card) și schimbați rolurile în echipă. |

Ordinea contează: întâi împărțirea și baseline-urile, apoi modelele, apoi pragul, iar testul abia la final.

---

## 11. Ce predați (slide 9)

- **Codul și fișierul de mediu** (de exemplu `requirements.txt`), ca oricine să poată rula proiectul și să obțină aceleași rezultate.
- **Tabelul de experimente:** fiecare încercare (ce model, ce setări, ce scor pe validare).
- **Model card:** un fel de „fișă tehnică” sau „prospect” al modelului. Ce face, pe ce date a fost antrenat, cât de bine merge, ce limite are și, foarte important, **la ce NU trebuie folosit** (de exemplu la refuzul automat al cererilor).
- **Nota de decizie:** de ce ați ales modelul și pragul respectiv, cu costurile asumate.
- **Demo de 5 minute.**

### Verificările de acceptare (obligatorii)

Dacă una lipsește, proiectul e considerat incomplet:
- [ ] nicio informație din viitor nu intră în feature-uri;
- [ ] împărțirea datelor e reproductibilă;
- [ ] există cel puțin două baseline-uri relevante;
- [ ] matricea de confuzie e completă;
- [ ] pragul nu e ales pe testul final;
- [ ] ați analizat cel puțin 10 erori;
- [ ] există o notă despre utilizarea permisă și cea interzisă.

**Bonus (stretch):** comparații pe subgrupuri sau pe perioade de timp, doar unde e legal și există suficiente date.

---

## 12. Rolurile în echipă (slide 10)

| Rol | Răspunde de |
|---|---|
| **Product owner** | Se asigură că știți ce face concret un om când vede semnalul „urgent”. |
| **Technical lead** | Verifică pipeline-ul. |
| **Evaluation lead** | Se ocupă de împărțirea datelor și de metrici. |
| **Implementation lead** | Antrenează modelele. |
| **Safety lead** | Verifică să nu existe leakage și că decizia rămâne la un om. |

Toți lucrează la tot, dar fiecare „semnează” pentru partea lui. Rolurile principale se rotesc la final, în L8.

---

## Pe scurt, într-o frază

Construiți un program care învață din tichete vechi să **semnaleze** tichetele noi care par urgente. Trebuie să demonstrați **cinstit** că e mai bun decât niște reguli simple, folosind măsuri potrivite (recall, precision, nu doar acuratețe). Pragul se alege după costul real al greșelilor, iar decizia finală rămâne mereu la un om.
