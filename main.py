import json
from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional
import os

# ===== OBSERVER PATTERN =====
class TransactionObserver(ABC):
    @abstractmethod
    def on_transaction(self, account: 'Account', transaction: 'Transaction'):
        pass

# ===== STRATEGY PATTERN (Interest Calculation) =====
class InterestStrategy(ABC):
    @abstractmethod
    def calculate_interest(self, balance: float) -> float:
        pass

class SavingsInterest(InterestStrategy):
    def calculate_interest(self, balance: float) -> float:
        return balance * 0.02  # 2% interest

class CheckingInterest(InterestStrategy):
    def calculate_interest(self, balance: float) -> float:
        return balance * 0.001  # 0.1% interest

class LoanInterest(InterestStrategy):
    def calculate_interest(self, balance: float) -> float:
        return balance * 0.05  # 5% interest (charged)

# ===== COMMAND PATTERN (Transactions) =====
class TransactionCommand(ABC):
    @abstractmethod
    def execute(self) -> bool:
        pass

    @abstractmethod
    def undo(self) -> bool:
        pass

class DepositCommand(TransactionCommand):
    def __init__(self, account: 'Account', amount: float):
        self.account = account
        self.amount = amount

    def execute(self) -> bool:
        return self.account.deposit(self.amount)

    def undo(self) -> bool:
        return self.account.withdraw(self.amount)

class WithdrawCommand(TransactionCommand):
    def __init__(self, account: 'Account', amount: float):
        self.account = account
        self.amount = amount

    def execute(self) -> bool:
        return self.account.withdraw(self.amount)

    def undo(self) -> bool:
        return self.account.deposit(self.amount)

class TransferCommand(TransactionCommand):
    def __init__(self, from_acct: 'Account', to_acct: 'Account', amount: float):
        self.from_acct = from_acct
        self.to_acct = to_acct
        self.amount = amount

    def execute(self) -> bool:
        if self.from_acct.withdraw(self.amount):
            return self.to_acct.deposit(self.amount)
        return False

    def undo(self) -> bool:
        if self.to_acct.withdraw(self.amount):
            return self.from_acct.deposit(self.amount)
        return False

# ===== CORE BANKING CLASSES =====
@dataclass
class Transaction:
    type: str  # "DEPOSIT", "WITHDRAWAL", "TRANSFER"
    amount: float
    timestamp: datetime

class Account:
    def __init__(self, account_id: str, owner: str, account_type: str):
        self.account_id = account_id
        self.owner = owner
        self.account_type = account_type
        self.balance = 0.0
        self.transaction_history: List[Transaction] = []
        self.observers: List[TransactionObserver] = []

        # Set interest strategy based on account type
        self.interest_strategy = {
            'savings': SavingsInterest(),
            'checking': CheckingInterest(),
            'loan': LoanInterest()
        }.get(account_type.lower(), SavingsInterest())

    def attach(self, observer: TransactionObserver):
        self.observers.append(observer)

    def deposit(self, amount: float) -> bool:
        if amount <= 0:
            return False
        self.balance += amount
        transaction = Transaction("DEPOSIT", amount, datetime.now())
        self.transaction_history.append(transaction)
        for observer in self.observers:
            observer.on_transaction(self, transaction)
        return True

    def withdraw(self, amount: float) -> bool:
        if amount <= 0 or amount > self.balance:
            return False
        self.balance -= amount
        transaction = Transaction("WITHDRAWAL", amount, datetime.now())
        self.transaction_history.append(transaction)
        for observer in self.observers:
            observer.on_transaction(self, transaction)
        return True

    def apply_interest(self):
        interest = self.interest_strategy.calculate_interest(self.balance)
        if interest != 0:
            self.deposit(interest)
        return interest

    def get_transaction_history(self) -> List[Transaction]:
        return self.transaction_history

    def __str__(self):
        return (f"Account ID: {self.account_id}\n"
                f"Owner: {self.owner}\n"
                f"Type: {self.account_type}\n"
                f"Balance: ${self.balance:.2f}")

class BankDatabase:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.accounts: Dict[str, Account] = {}
            cls._instance.load_data()
        return cls._instance

    def add_account(self, account: Account):
        self.accounts[account.account_id] = account

    def get_account(self, account_id: str) -> Optional[Account]:
        return self.accounts.get(account_id)

    def get_all_accounts(self) -> List[Account]:
        return list(self.accounts.values())

    def save_data(self):
        data = {
            'accounts': [
                {
                    'account_id': acct.account_id,
                    'owner': acct.owner,
                    'account_type': acct.account_type,  # Now saving account_type
                    'balance': acct.balance,
                    'transactions': [
                        {'type': txn.type, 'amount': txn.amount, 'timestamp': txn.timestamp.isoformat()}
                        for txn in acct.transaction_history
                    ]
                }
                for acct in self.accounts.values()
            ]
        }
        with open('bank_data.json', 'w') as f:
            json.dump(data, f, indent=2)

    def load_data(self):
        try:
            with open('bank_data.json', 'r') as f:
                data = json.load(f)
                for acct_data in data['accounts']:
                    # Handle missing account_type by defaulting to 'savings'
                    account_type = acct_data.get('account_type', 'savings')
                    account = Account(
                        acct_data['account_id'],
                        acct_data['owner'],
                        account_type
                    )
                    account.balance = acct_data['balance']
                    account.transaction_history = [
                        Transaction(
                            txn['type'],
                            txn['amount'],
                            datetime.fromisoformat(txn['timestamp'])
                        )
                        for txn in acct_data.get('transactions', [])
                    ]
                    self.accounts[account.account_id] = account
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load data ({str(e)}. Starting with fresh database.")
            self.accounts = {}\

class TransactionLogger(TransactionObserver):
    def on_transaction(self, account: Account, transaction: Transaction):
        print(f"\n[Transaction Log] {account.account_id}: "
              f"{transaction.type} of ${transaction.amount:.2f} "
              f"at {transaction.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

# ===== INTERACTIVE BANKING SYSTEM =====
class InteractiveBankSystem:
    def __init__(self):
        self.database = BankDatabase()
        self.transaction_logger = TransactionLogger()
        self.undo_stack: List[TransactionCommand] = []
        self.current_customer = None

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def show_menu(self):
        self.clear_screen()
        print("\n=== BANKING SYSTEM ===")
        print(f"Customer: {self.current_customer if self.current_customer else 'Not logged in'}")
        print("1. Create Account")
        print("2. Deposit")
        print("3. Withdraw")
        print("4. Transfer")
        print("5. View Account")
        print("6. View Transaction History")
        print("7. Apply Interest")
        print("8. Undo Last Transaction")
        print("9. Switch Customer")
        print("10. List All Accounts")
        print("0. Exit")

    def create_account(self):
        self.clear_screen()
        print("\n=== CREATE ACCOUNT ===")
        account_id = input("Enter account ID: ")
        if self.database.get_account(account_id):
            print("Error: Account ID already exists!")
            input("Press Enter to continue...")
            return

        owner = input("Enter owner name: ")
        print("\nAccount Types:")
        print("1. Savings (2% interest)")
        print("2. Checking (0.1% interest)")
        print("3. Loan (5% interest charge)")
        choice = input("Select account type (1-3): ")

        account_type = {
            '1': 'savings',
            '2': 'checking',
            '3': 'loan'
        }.get(choice, 'savings')

        account = Account(account_id, owner, account_type)
        account.attach(self.transaction_logger)
        self.database.add_account(account)
        print(f"\nAccount created successfully!\n{account}")
        input("\nPress Enter to continue...")

    def deposit(self):
        self.clear_screen()
        print("\n=== DEPOSIT ===")
        account_id = input("Enter account ID: ")
        account = self.database.get_account(account_id)
        if not account:
            print("Error: Account not found!")
            input("Press Enter to continue...")
            return

        try:
            amount = float(input("Enter amount to deposit: $"))
            cmd = DepositCommand(account, amount)
            if cmd.execute():
                self.undo_stack.append(cmd)
                print(f"\nDeposit successful! New balance: ${account.balance:.2f}")
            else:
                print("\nError: Invalid deposit amount!")
        except ValueError:
            print("\nError: Please enter a valid number!")
        input("\nPress Enter to continue...")

    def withdraw(self):
        self.clear_screen()
        print("\n=== WITHDRAW ===")
        account_id = input("Enter account ID: ")
        account = self.database.get_account(account_id)
        if not account:
            print("Error: Account not found!")
            input("Press Enter to continue...")
            return

        try:
            amount = float(input("Enter amount to withdraw: $"))
            cmd = WithdrawCommand(account, amount)
            if cmd.execute():
                self.undo_stack.append(cmd)
                print(f"\nWithdrawal successful! New balance: ${account.balance:.2f}")
            else:
                print("\nError: Invalid withdrawal amount or insufficient funds!")
        except ValueError:
            print("\nError: Please enter a valid number!")
        input("\nPress Enter to continue...")

    def transfer(self):
        self.clear_screen()
        print("\n=== TRANSFER ===")
        from_id = input("Enter source account ID: ")
        to_id = input("Enter destination account ID: ")

        from_acct = self.database.get_account(from_id)
        to_acct = self.database.get_account(to_id)

        if not from_acct or not to_acct:
            print("Error: One or both accounts not found!")
            input("Press Enter to continue...")
            return

        try:
            amount = float(input(f"Enter amount to transfer (max ${from_acct.balance:.2f}): $"))
            cmd = TransferCommand(from_acct, to_acct, amount)
            if cmd.execute():
                self.undo_stack.append(cmd)
                print(f"\nTransfer successful!")
                print(f"Source account new balance: ${from_acct.balance:.2f}")
                print(f"Destination account new balance: ${to_acct.balance:.2f}")
            else:
                print("\nError: Invalid transfer amount or insufficient funds!")
        except ValueError:
            print("\nError: Please enter a valid number!")
        input("\nPress Enter to continue...")

    def view_account(self):
        self.clear_screen()
        print("\n=== ACCOUNT DETAILS ===")
        account_id = input("Enter account ID: ")
        account = self.database.get_account(account_id)
        if account:
            print(f"\n{account}")
        else:
            print("\nError: Account not found!")
        input("\nPress Enter to continue...")

    def view_transaction_history(self):
        self.clear_screen()
        print("\n=== TRANSACTION HISTORY ===")
        account_id = input("Enter account ID: ")
        account = self.database.get_account(account_id)
        if not account:
            print("Error: Account not found!")
            input("Press Enter to continue...")
            return

        print(f"\nTransaction history for {account.account_id}:")
        for txn in account.get_transaction_history():
            print(f"{txn.timestamp.strftime('%Y-%m-%d %H:%M')}: "
                  f"{txn.type.ljust(10)} ${txn.amount:>8.2f}")

        input("\nPress Enter to continue...")

    def apply_interest(self):
        self.clear_screen()
        print("\n=== APPLY INTEREST ===")
        account_id = input("Enter account ID: ")
        account = self.database.get_account(account_id)
        if not account:
            print("Error: Account not found!")
            input("Press Enter to continue...")
            return

        interest = account.apply_interest()
        if interest != 0:
            print(f"\nInterest applied: ${interest:.2f}")
            print(f"New balance: ${account.balance:.2f}")
        else:
            print("\nNo interest applied (zero balance or checking account)")
        input("\nPress Enter to continue...")

    def undo_transaction(self):
        self.clear_screen()
        print("\n=== UNDO TRANSACTION ===")
        if not self.undo_stack:
            print("No transactions to undo!")
            input("Press Enter to continue...")
            return

        cmd = self.undo_stack.pop()
        if cmd.undo():
            print("\nTransaction successfully undone!")
        else:
            print("\nError: Failed to undo transaction!")
        input("\nPress Enter to continue...")

    def switch_customer(self):
        self.clear_screen()
        print("\n=== SWITCH CUSTOMER ===")
        self.current_customer = input("Enter customer name: ")
        print(f"\nNow operating as {self.current_customer}")
        input("\nPress Enter to continue...")

    def list_accounts(self):
        self.clear_screen()
        print("\n=== ALL ACCOUNTS ===")
        accounts = self.database.get_all_accounts()
        if not accounts:
            print("No accounts found!")
        else:
            for account in accounts:
                print(f"{account.account_id.ljust(10)} {account.owner.ljust(20)} "
                      f"{account.account_type.ljust(10)} ${account.balance:>8.2f}")
        input("\nPress Enter to continue...")

    def run(self):
        while True:
            self.show_menu()
            choice = input("\nEnter your choice (0-10): ")

            if choice == '0':
                self.database.save_data()
                print("\nExiting banking system. Goodbye!")
                break
            elif choice == '1':
                self.create_account()
            elif choice == '2':
                self.deposit()
            elif choice == '3':
                self.withdraw()
            elif choice == '4':
                self.transfer()
            elif choice == '5':
                self.view_account()
            elif choice == '6':
                self.view_transaction_history()
            elif choice == '7':
                self.apply_interest()
            elif choice == '8':
                self.undo_transaction()
            elif choice == '9':
                self.switch_customer()
            elif choice == '10':
                self.list_accounts()
            else:
                print("\nInvalid choice! Please try again.")
                input("Press Enter to continue...")

if __name__ == "__main__":
    bank_system = InteractiveBankSystem()
    bank_system.run()
