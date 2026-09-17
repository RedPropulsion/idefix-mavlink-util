# Idefix / ObeliCS MAVLink command tool

Questo tool viene eseguito su Idefix per inviare a ObeliCS i comandi MAVLink
del micro-dialetto di progetto. La modalità `listen` permette inoltre di usare
un PC come simulatore temporaneo di ObeliCS.

Ogni funzione ha un proprio command ID; tutti vengono trasportati nel messaggio
standard `COMMAND_LONG`, con `param1` ... `param7` impostati a zero:

| Attuatore | Comando | ID |
|---|---|---:|
| LED | `MAV_CMD_OBELICS_LED_OFF` | 60000 |
| LED | `MAV_CMD_OBELICS_LED_BOUNCE` | 60001 |
| LED | `MAV_CMD_OBELICS_LED_SPIN` | 60002 |
| LED | `MAV_CMD_OBELICS_LED_BLINK` | 60003 |
| Servo | `MAV_CMD_OBELICS_SERVO_OFF` | 60010 |
| Servo | `MAV_CMD_OBELICS_SERVO_WIGGLE` | 60011 |
| Servo | `MAV_CMD_OBELICS_SERVO_SWEEP` | 60012 |
| Servo | `MAV_CMD_OBELICS_SERVO_HELLO` | 60013 |

ObeliCS risponde con il messaggio standard `COMMAND_ACK`: usa
`MAV_RESULT_ACCEPTED` per un comando eseguito e `MAV_RESULT_UNSUPPORTED` per un
command ID sconosciuto.

Il tool Python usa il dialect `common`: non serve generare un binding Python
finché il progetto aggiunge soltanto nuovi valori a `MAV_CMD`. Gli otto numeri
qui sopra devono però restare identici a quelli dichiarati in `obelics.xml`.

## 1. Copia il tool su Idefix

Dal PC, nella cartella che contiene `idefix-mavlink-tool`:

```bash
scp -r idefix-mavlink-tool pi@IP_IDEFIX:~/
```

Sostituire `pi` con l'utente SSH e `IP_IDEFIX` con l'indirizzo Ethernet reale.

## 2. Prepara l'ambiente Python

Su Idefix:

```bash
cd ~/idefix-mavlink-tool
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Per eseguire anche il simulatore `listen` su un PC, ripetere gli stessi passaggi
in una copia locale della cartella.

## 3. Avvia ObeliCS o il simulatore

Se l'hardware ObeliCS non è ancora disponibile, sul PC che lo simula:

```bash
cd ~/idefix-mavlink-tool
source .venv/bin/activate
python3 idefix_mavlink.py listen
```

Il listener usa UDP 14550 su tutte le interfacce e si presenta come MAVLink
system 1, component 1. Se è attivo un firewall, aprire la porta UDP 14550.

## 4. Invia da Idefix

Esempi, sostituendo `192.168.1.100` con l'IP Ethernet di ObeliCS o del PC che lo
sta simulando:

```bash
source .venv/bin/activate
python3 idefix_mavlink.py send --host 192.168.1.100 servo wiggle
python3 idefix_mavlink.py send --host 192.168.1.100 led bounce
python3 idefix_mavlink.py send --host 192.168.1.100 led off
```

Il test è riuscito quando su Idefix compare `ACK MAV_RESULT_ACCEPTED` e sul
ricevitore compare la riga `RX` con attuatore, funzione, mittente e sequence
number.

Per provare tutte le otto modalità:

```bash
python3 idefix_mavlink.py test-all --host 192.168.1.100
```

Per usare il simulatore come un piccolo menu testuale:

```bash
python3 idefix_mavlink.py interactive --host 192.168.1.100
```

Nella console si possono digitare, per esempio, `servo hello`, `led blink`,
`servo off` e `quit`. Per compatibilità, `none` è accettato come alias di `off`.

## Diagnostica rapida

Verificare prima la connettività da Idefix:

```bash
ping IP_OBELICS
```

Sul dispositivo che esegue `listen`, controllare che il processo sia in ascolto:

```bash
ss -lunp | grep 14550
```

Se il ricevitore mostra `RX`, ma Idefix non vede l'ACK, controllare firewall,
routing e configurazione della porta remota di ObeliCS. Il sender riprova due
volte per impostazione predefinita; timeout e tentativi sono modificabili con
`--timeout` e `--retries`.

## Test locali

Test delle codifiche:

```bash
python3 -m unittest -v
```

Test UDP completo sullo stesso computer, in due terminali:

```bash
python3 idefix_mavlink.py listen --bind 127.0.0.1 --count 8
python3 idefix_mavlink.py test-all --host 127.0.0.1
```

## Allineamento con il firmware

Quando cambia un valore in `obelics.xml`, aggiornare la costante omonima in
`idefix_mavlink.py` e rieseguire i test. Se in futuro verranno aggiunti messaggi
personalizzati, oltre alle entry di `MAV_CMD`, sarà opportuno generare anche il
binding Python del dialect.
