# Auto Clicker (Wayland)

Полноценная десктопная программа автокликера для Linux под Wayland —
аналог OP Auto Clicker для Windows, но без X11 и без внешних утилит
(`xdotool` / `ydotool` не используются вообще). Клики отправляются напрямую
в подсистему ввода Linux через виртуальное устройство **`uinput`**.

Работает на CachyOS / Arch с композиторами **niri, Hyprland, Sway, GNOME,
KDE, labwc** и любыми другими Wayland-композиторами.

---

## Возможности

- **Главное окно:** кнопки ▶ Start / ■ Stop, индикатор состояния
  (Running / Stopped), счётчик кликов, время работы, реальный **CPS**
  (кликов в секунду).
- **Настройки кликов:**
  - интервал в **мс / сек / мин / час**;
  - кнопка мыши: **левая / правая / средняя**;
  - тип: **одиночный / двойной** клик;
  - режим: **continuous / toggle / hold**;
  - горячая клавиша через диалог **«Press any key…»** (назначается любая
    клавиша или кнопка мыши);
  - **рандомизация** интервала ±N% (с переключателем).
- **Профили:** Minecraft, Roblox, Cookie Clicker, Mining, «Профиль 1/2/3» и
  любые свои. Сохранение, удаление, **экспорт/импорт JSON** (при импорте
  имя автоматически разрешается от коллизий).
- **Настройки приложения:** автозапуск с системой, сворачивание в трей,
  закрытие в трей, фоновая работа, автосохранение.
- **Тёмная тема**, современные кнопки, анимированные переключатели, иконки,
  аккуратные отступы.
- **Потокобезопасность:** клики крутятся в отдельном потоке (`QThread`),
  GUI не замирает; синхронизация через `threading.Lock` + прерываемый
  `threading.Event` (без busy-loop), тайминги точные.
- **Авто-детект ограничений Wayland:** если глобальные горячие клавиши
  недоступны (нет прав на `/dev/input`), программа честно показывает
  понятное сообщение и предлагает альтернативу (кнопки Start/Stop или
  биндинг композитора).

---

## Требования

- Linux с Wayland-сессией.
- Python 3.12+ (пакет сам создаёт изолированное окружение через `uv`,
  системный `pip` не нужен).
- Пользователь должен состоять в группе **`uinput`**, чтобы писать в
  `/dev/uinput` (для кликов **без root**):

  ```bash
  sudo usermod -aG uinput "$USER"
  # перелогиньтесь или перезапустите сессию
  ```

  Проверить: `ls -l /dev/uinput` и `groups | grep uinput`.

- Для **глобальных** горячих клавиш (работающих в любом окне) нужен доступ
  на чтение `/dev/input/event*` — то есть быть в группе **`input`** или
  запускать от root. Без этого горячая клавиша не сработает системно, но
  кнопки Start/Stop в окне программы продолжают работать.

---

## Установка и запуск

```bash
git clone <repo> && cd AutoClicker
./run.sh            # первый запуск создаёт venv (uv) и ставит PySide6
```

`run.sh` сам:
1. при необходимости создаёт виртуальное окружение (`uv venv`);
2. ставит `PySide6`;
3. очищает `PYTHONHOME`/`PYTHONPATH` (чтобы не мешал «родительский» AppImage
   Python) и запускает `python -m autoclicker`.

Запуск напрямую (если окружение уже готово):

```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/python -m autoclicker
```

Полезные ключи:

- `--start-minimized` — запустить свёрнутым (в трей, если доступен);
- `--self-test` — запустить, поработать ~1.5 с и выйти (для тестов);
- `--version`.

---

## Глобальные горячие клавиши (кроссплатформенная система бэкендов)

Горячая клавиша работает через единый интерфейс `HotkeyBackend`. Конкретный
механизм выбирается автоматически по платформе и доступным возможностям
(либо принудительно в «App settings → Global hotkey backend»: **Auto / Evdev /
IPC / X11**). Сервис `HotkeyService` ничего не знает о конкретной реализации —
только об интерфейсе.

Приоритет выбора (`Auto`):

1. **Evdev** (`/dev/input/event*`) — чтение raw-событий клавиатуры напрямую.
   Работает в **любом** окне, независимо от фокуса. Нужен доступ на чтение
   `/dev/input/event*`: группа **`input`** или root.
2. **IPC** (Unix-socket) — если `/dev/input` недоступен (типично для Wayland
   без группы `input`). Приложение открывает сокет
   `$XDG_RUNTIME_DIR/autoclicker.sock` и слушает команды. В этом режиме
   **не нужны никакие спец-права** — горячую клавишу биндит сам композитор на
   утилиту **`autoclickerctl`**.
3. **X11** — настоящий `XGrabKey` через `ctypes` (только X11-сессии).
4. **Windows** — `RegisterHotKey` (Win32; архитектура готова, код активен
   только на Windows).
5. **Dummy** — безопасный fallback, если ничего не доступно.

Статус показывается в главном окне:
`✔ Global hotkey active` / `✔ IPC mode active` / `⚠ Global hotkey unavailable`.
Страница **Tools → Diagnostics** честно показывает Wayland/X11, композитор,
доступность `/dev/input` и `/dev/uinput`, IPC и причину, почему каждый бэкенд
недоступен (без «тихих» ошибок).

### Привязка композитора (режим IPC)

В диалоге назначения горячей клавиши в режиме IPC показаны готовые примеры.
Скопируйте нужный в конфиг композитора и перезагрузите его:

```kdl
# niri (~/.config/niri/config.kdl)
binds {
    "F8" { spawn "autoclickerctl" "toggle"; }
}
```

```text
# Sway (~/.config/sway/config)
bindsym F8 exec autoclickerctl toggle

# Hyprland (~/.config/hypr/hyprland.conf)
bind = , F8, exec, autoclickerctl toggle
```

Утилита `autoclickerctl` принимает команды: **`start` | `stop` | `toggle` |
`pause`**. Она лежит рядом с `run.sh`:

```bash
./autoclickerctl toggle
```

Если `/dev/input` доступен (группа `input`), горячая клавиша, назначенная
в диалоге «Press any key…», сработает глобально через мониторинг
`/dev/input/event*` (бэкенд Evdev).

---

## Архитектура

```
AutoClicker/
├── run.sh                      # лаунчер (venv + очистка окружения)
├── requirements.txt            # PySide6
├── assets/autoclicker.desktop  # шаблон .desktop для ручной установки
├── autoclicker/
│   ├── __main__.py             # точка входа (python -m autoclicker)
│   ├── __init__.py             # версия
│   ├── utils/                  # logging_setup, platform, timeutil
│   ├── input/                  # key_codes, virtual_device (uinput),
│   │                           #   hotkey_backends (evdev / IPC / X11 / Windows / Dummy)
│   ├── core/                   # models (dataclasses), click_engine (QThread)
│   ├── services/               # settings, profiles, autostart, tray, hotkey_service
│   ├── gui/                    # theme (QSS), components, main_window, dialogs
│   └── ctl.py                  # autoclickerctl — IPC-клиент (start/stop/toggle/pause)
└── tests/
    ├── offscreen_smoke.py       # Headless-интеграционный тест
    └── test_hotkey_backends.py  # Тесты каждого backend'а (evdev/IPC/X11/Windows/Dummy)
```

Принципы: OOP, SOLID/DRY/KISS, type hints, dataclasses, централизованное
логирование, обработка ошибок. GUI и клики разделены потоками; общение —
через Qt-сигналы.

---

## Тестирование (headless)

```bash
source .venv/bin/activate

# Интеграционный smoke-тест (движок + профили + реальное uinput-устройство)
QT_QPA_PLATFORM=offscreen python tests/offscreen_smoke.py

# Тесты каждого hotkey-бэкенда (evdev через синтетический fd, IPC через
# реальный Unix-сокет + autoclickerctl, X11/Windows/Dummy — безопасный lifecycle)
QT_QPA_PLATFORM=offscreen python tests/test_hotkey_backends.py
```

Проверяется: поток движка запускается, создаётся реальное `uinput`-устройство
и выполняется клик, профили сохраняются/читаются/удаляются, цикл
Start→Stop корректно меняет состояние, а также корректная доставка сигналов,
захват/сброс захвата клавиши и чистое завершение потоков для всех бэкендов.

---

## Заметки по безопасности

- Никаких shell-команд для кликов: только `ctypes` + `uinput`.
- Глобальная горячая клавиша — через `HotkeyBackend`: evdev читает
  `/dev/input` блокирующим `os.read` (без polling), IPC блокирует на
  `accept()`/`recv()` с таймаутом, X11 — на `select()` по fd соединения.
  Все потоки — daemon и корректно завершаются в `stop()` (join с таймаутом).
- При отсутствии прав бэкенд честно помечается недоступным (без «тихих»
  ошибок) и предлагает альтернативу (IPC-биндинг композитора).
- Данные хранятся в `~/.config/autoclicker/` (настройки и профили) и
  `~/.cache/autoclicker/autoclicker.log`.
