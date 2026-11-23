# MVKView — 80-битная исходная константа интегрирования и парные стадии спектра

23.11.2026. Только исследовательская ветка. Приватные оригиналы не публиковались.

По локальным Projects.7z/_Unit115.pas + mvkview.idp + mvk_idr(1).sqlite восстановлена исходная константа Extended по адресу 007D219C: 159.154943091895335768870545223308. Старое значение 159.154943091895 было усечено. В цикле 007D2164 выполняются Extended /bin, *stored Single(N/Fs), квадрат и *Single(Power), затем FSTP Single после каждого прохода. Tag2 — один проход, Tag3 — два.

Исправлена основная Python функция _delphi_integration_power: использует полную исходную Extended константу и np.longdouble на поддерживаемой x86 платформе, сохраняя Float32-store после каждого прохода. На Windows NumPy longdouble может соответствовать Float64: такой результат остаётся кандидатом, а не доказательством original Delphi x87. В независимом C QA указана точная source-derived 80-bit константа. Оригинальные байты в репозиторий не копировались.

Расширен Linux CI: независимое полное сравнение Power Single для N=1024/4096/65536/262144, Fs=512/2048/65536, одного/двух интегрирований и сохранения входного окна. Прежняя сквозная цепочка Hann → FFT → Power → четыре Y остаётся.

Локально независимо до GitHub C/x87 vs NumPy longdouble, synthetic only: 0 различий для N=1024/4096/8192/65536/262144, включая Fs 512/2048/65536 и оба прохода. Это НЕ данные оригинального запущенного Delphi.

Локальный read-only comparator original_mode2_paired_acceptance дополнен пятью этапами спектра: Pre-Hann, Windowed, FFT Complex (interleaved Single Re/Im), Power postmode и Y (в дополнение к существующему Power). Это помогает собрать одну сравниваемую пару original/Native на идентичном RAW, затем WriteData BIN/TSXML, WriteValues/TABLE. В отчёте отмечаются наличие семейств и количество Y, но original Win32 Stop boundary остаётся false. Синтетический тест выявляет одиночное битовое изменение при неизменном RAW и отвергает изменившийся RAW.

Открыто: одинаковый физический original Win32/Go RX + source Hann/FFT/Power/Postmode/Y, реальный оригинальный CW, GetSignal, WriteValues/WriteData/Stop и обратные ошибки/переподключение. original_delphi_compatibility_verified=false; physical_mvk01_e2e_verified=false; same_physical_capture_authenticated=false. Main и транспорт не менялись. Новый CI проверить по SHA.