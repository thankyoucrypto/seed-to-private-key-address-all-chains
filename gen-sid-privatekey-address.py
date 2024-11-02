from hdwallet.cryptocurrencies import ( EthereumMainnet, DashMainnet, TronMainnet, # noqa
    DogecoinMainnet, LitecoinMainnet, BitcoinMainnet, AtomMainnet) # noqa
from hdwallet.derivations import BIP44Derivation
from colorama import init, Fore, Style
from datetime import datetime
import multiprocessing
import hdwallet
import logging
import time
import os

# --------------------------- INFORMATION ---------------------------
#
#       > Скрипт преобразует сид фраза -> приватник -> адресс для разных сетей.
#
#       Функционал:
#
#       1. Из сид-фразы  -> приватник и адресс (+ Настройка глубина адреса)
#       2. Из приватника -> адресс
#
#       Поддерживаемые сети: eth, btc, ltc, doge, dash, atom, trx
#       На выходе результаты будут в файле в формате mnemonic, private_key, address
#
# ---------------------------  КОНФИГУРАЦИЯ ---------------------------

# Входной тип данных кошельков
WALLETS_DATA_TYPE = 'mnemonic'         # mnemonic | private_key

# Путь к файлу с данными кошельков
WALLETS_DATA_FILE = r"wallet_data.txt"

# Количество адресов для генерации. Пояснение: По стандарту BIP44 (и его производным) сид-фраза позволяет генерировать иерархию адресов. То есть, на основе одной сид-фразы можно создать множество уникальных адресов, каждый из которых находится на определенной позиции иерархии, определяемой индексом адреса.
ADDRESS_DEPTH = 2  # Только для WALLETS_DATA_TYPE = 'mnemonic'

# Блокчейны для которых не надо - закомментируйте
NETWORK_MAP = {
    "eth": EthereumMainnet,
    # "btc": BitcoinMainnet,
    # "ltc": LitecoinMainnet,
    # "doge": DogecoinMainnet,
    # "dash": DashMainnet,
    # "atom": AtomMainnet,
    # "trx": TronMainnet,
}

# ---------------------------  НЕОБЯЗАТЕЛЬНАЯ КОНФИГУРАЦИЯ ---------------------------

RESULT_FOLDER = 'RESULT_GEN'                    # Название папки для результатов
PROCESS_COUNT = multiprocessing.cpu_count() - 2 # Количество процессов для параллельной работы. Оптимально: multiprocessing.cpu_count() - 2

# ------------------------------- END CONFIG -------------------------------

# Инициализация Colorama
init(autoreset=True)

class ColoredFormatter(logging.Formatter):
    """Класс для цветного форматирования логов."""

    COLOR_MAP = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def format(self, record):
        # Получаем цвет на основе уровня логирования
        color = self.COLOR_MAP.get(record.levelno, Fore.WHITE)
        # Оборачиваем сообщение в цвет
        record.msg = f"{color}{record.msg}{Style.RESET_ALL}"
        return super().format(record)


# Настройка логирования
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # Установите желаемый уровень логирования

# Создаем обработчик и устанавливаем формат
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter("%(asctime)s - %(levelname)s - %(message)s"))

# Добавляем обработчик к логгеру
logger.addHandler(console_handler)


# Создает папку для результатов с указанием даты и времени запуска
def setup_result_folder() -> str:
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    folder_path = os.path.join(RESULT_FOLDER, timestamp)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


# Сохраняет все данные в файл в папке результатов для заданной сети
def save_results(result_folder: str, network_code: str, results: list[str]):
    if not results:
        return
    filename = f"{network_code}.txt"
    filepath = os.path.join(result_folder, filename)
    with open(filepath, 'a') as file:
        file.write('\n'.join(results) + '\n')


# Выводит начальную информацию о настройках
def print_initial_info():
    # Считаем количество строк в файле с данными кошельков
    with open(WALLETS_DATA_FILE, 'r') as file:
        lines = file.readlines()
        wallet_count = len(lines)

    print(Fore.CYAN + "----- Начальная информация -----")
    print(Fore.YELLOW + f"Входные данные: {WALLETS_DATA_TYPE}")
    print(Fore.YELLOW + f"Количество:     {wallet_count}")
    if WALLETS_DATA_TYPE == 'mnemonic':
        print(Fore.YELLOW + f"Глубина генерации адреса: {ADDRESS_DEPTH}")

    print(Fore.CYAN + "------------------------------")
    print(Fore.GREEN + f"Генерируем на {PROCESS_COUNT} ядрах, старт через 5 сек...\n")
    time.sleep(5)  # Задержка перед началом процесса


# Приватни из сид-фразы
def generate_private_key_from_mnemonic(mnemonic_phrase: str, network_code: str, address_index: int = 0) -> str:
    selected_network = NETWORK_MAP.get(network_code)
    if not selected_network:
        logging.error(f"Сеть '{network_code}' не поддерживается.")
        return ""

    try:
        wallet = hdwallet.BIP44HDWallet(cryptocurrency=selected_network)
        wallet.from_mnemonic(mnemonic=mnemonic_phrase, language="english", passphrase=None)
        wallet.clean_derivation()
        derivation_path = BIP44Derivation(cryptocurrency=selected_network, account=0, change=False,
                                          address=address_index)
        wallet.from_path(path=derivation_path)
        private_key = wallet.private_key()
        return private_key
    except Exception as error:
        logging.error(f"Ошибка генерации приватного ключа для {network_code} c глубиной {address_index}: {error}")
        # logging.debug(traceback.format_exc())
        return ""


# Адрес из сид фразы
def generate_addresses_from_mnemonic(mnemonic_phrase: str, network_code: str, depth: int) -> list[tuple[str, str]]:
    addresses = []
    for address_index in range(depth):
        private_key = generate_private_key_from_mnemonic(mnemonic_phrase, network_code, address_index)
        address = generate_address_from_private_key(private_key, network_code)
        if private_key and address:
            addresses.append((private_key, address))
    return addresses


# Адрес из приватника
def generate_address_from_private_key(private_key: str, network_code: str) -> str:
    selected_network = NETWORK_MAP.get(network_code)
    if not selected_network:
        logging.error(f"Сеть '{network_code}' не поддерживается.")
        return ""

    try:
        wallet = hdwallet.BIP44HDWallet(cryptocurrency=selected_network)
        wallet.from_private_key(private_key=private_key)
        address = wallet.address()
        return address
    except Exception as error:
        logging.error(f"Ошибка генерации адреса для {network_code}: {error}")
        # logging.debug(traceback.format_exc())
        return ""


# Для 1 потока - обрабатывает часть данных о кошельках
def process_wallet_data_chunk(wallet_data_chunk: list[str], result_folder: str):
    results = {network_code: [] for network_code in NETWORK_MAP.keys()}
    for data in wallet_data_chunk:
        data = data.strip()
        logging.debug(f"Работаем с: {data}...")

        if WALLETS_DATA_TYPE == 'mnemonic':
            for network_code in NETWORK_MAP:
                addresses = generate_addresses_from_mnemonic(data, network_code, ADDRESS_DEPTH)
                for private_key, address in addresses:
                    result_data = f"{data}, {private_key}, {address}"
                    results[network_code].append(result_data)

        elif WALLETS_DATA_TYPE == 'private_key':
            for network_code in NETWORK_MAP:
                address = generate_address_from_private_key(data, network_code)
                if address:
                    result_data = f", {data}, {address}"  # Пустая сид-фраза, приватный ключ, адрес
                    results[network_code].append(result_data)

        elif WALLETS_DATA_TYPE == 'address':
            logging.info("Тип данных 'address' не требует дальнейшей обработки.")

    # Сохраняем результаты в файлы
    for network_code, network_results in results.items():
        save_results(result_folder, network_code, network_results)


# Основная функция - запуск в мультипотоке
def process_wallet_data():
    result_folder = setup_result_folder()
    print_initial_info()

    try:
        with open(WALLETS_DATA_FILE, 'r') as file:
            lines = file.readlines()
            total_wallets = len(lines)

            # Разбиваем данные на куски для обработки в параллельных процессах
            chunk_size = total_wallets // PROCESS_COUNT
            wallet_data_chunks = [lines[i:i + chunk_size] for i in range(0, total_wallets, chunk_size)]

            with multiprocessing.Pool(processes=PROCESS_COUNT) as pool:
                pool.starmap(process_wallet_data_chunk, [(chunk, result_folder) for chunk in wallet_data_chunks])

    except FileNotFoundError:
        logging.error(f"Файл с данными кошельков '{WALLETS_DATA_FILE}' не найден.")

    print(f'Программа успешно завершена.\nРезультаты записаны в папку {result_folder}')


# Запуск обработки
if __name__ == "__main__":
    process_wallet_data()

