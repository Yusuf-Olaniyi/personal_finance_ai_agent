from csv_parser import parse_expense_csv
print(parse_expense_csv(open("sample_expenses.csv", "rb").read()))