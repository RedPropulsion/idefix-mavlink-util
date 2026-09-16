# ObeliCS / Idefix MAVLink test tool

Questo tool usa il PC come simulatore di ObeliCS e verifica la comunicazione
MAVLink bidirezionale via Ethernet con Idefix.

Per questa prima simulazione non serve un dialect MAVLink personalizzato:

| Attuatore | Messaggio | `command` | `param1` |
|---|---|---:|---|
| Servo | `COMMAND_LONG` | `MAV_CMD_USER_1` (31010) | 0 NONE, 1 WIGGLE, 2 SWEEP, 3 HELLO |
| LED | `COMMAND_LONG` | `MAV_CMD_USER_2` (31011) | 0 NONE, 1 SPIN, 2 BLINK, 3 BOUNCE |

Idefix risponde a ogni comando valido con un `COMMAND_ACK` di tipo
`MAV_RESULT_ACCEPTED`. In questa fase il ricevitore verifica e stampa il comando,
ma non pilota hardware.

## 1. Copia su Idefix

Dal PC, nella cartella che contiene `idefix-mavlink-tool`:

```bash
scp -r idefix-mavlink-tool pi@IP_IDEFIX:~/
```

Sostituire `pi` con l'utente SSH e `IP_IDEFIX` con l'indirizzo Ethernet reale.

## 2. Prepara i due ambienti

Eseguire sia sul PC sia su Idefix:

```bash
cd ~/idefix-mavlink-tool
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Se sul PC la cartella si trova altrove, usare naturalmente il suo percorso reale.

## 3. Avvia il ricevitore su Idefix

Nella sessione SSH:

```bash
cd ~/idefix-mavlink-tool
source .venv/bin/activate
python3 idefix_mavlink.py listen
```

Il listener usa UDP 14550 su tutte le interfacce. Se è attivo un firewall, aprire
la porta UDP 14550. Non è necessario avviare il programma con `sudo`.

## 4. Invia dal PC

Esempi, sostituendo `192.168.1.50` con l'IP Ethernet di Idefix:

```bash
source .venv/bin/activate
python3 idefix_mavlink.py send --host 192.168.1.50 servo wiggle
python3 idefix_mavlink.py send --host 192.168.1.50 led bounce
```

Il test è riuscito quando sul PC compare `ACK MAV_RESULT_ACCEPTED` e su Idefix
compare la riga `RX` con attuatore, modalità, mittente e sequence number.

Per provare tutte le otto modalità:

```bash
python3 idefix_mavlink.py test-all --host 192.168.1.50
```

Per usare il simulatore come un piccolo menu testuale:

```bash
python3 idefix_mavlink.py interactive --host 192.168.1.50
```

Nella console si possono digitare, per esempio, `servo hello`, `led blink` e
`quit`.

## Diagnostica rapida

Verificare prima la connettività dal PC:

```bash
ping IP_IDEFIX
```

Controllare su Idefix che il processo sia in ascolto:

```bash
ss -lunp | grep 14550
```

Se Idefix mostra `RX`, ma il PC non vede l'ACK, controllare firewall e routing in
direzione Raspberry -> PC. Il sender riprova due volte per impostazione predefinita;
timeout e tentativi sono modificabili con `--timeout` e `--retries`.

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

## Passo successivo

Quando i comandi reali saranno definiti, conviene creare un dialect XML del
progetto con messaggi espliciti e campi tipizzati, invece di continuare a usare
`MAV_CMD_USER_1/2`. La struttura del tool permette di sostituire la codifica senza
cambiare il flusso UDP e la logica ACK.
