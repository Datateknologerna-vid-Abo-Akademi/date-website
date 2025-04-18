import gspread

class DateSheetsAdapter:
    def __init__(self, service_account: dict, sheet: str, worksheet: str):
        self.client = gspread.service_account_from_dict(service_account)
        self.sheet = self.client.open_by_key(sheet).worksheet(worksheet)

    def change_sheet(self, sheet: str, worksheet: str):
        self.sheet = self.client.open_by_key(sheet).worksheet(worksheet)

    def append_row(self, data: list):
        self.sheet.append_row(data)

    def get_column_by_name(self, name: str):
        rowvals = self.sheet.row_values(1)
        return rowvals.index(name) + 1

    def get_row_values(self, row: int) -> list:
        return self.sheet.row_values(row)

    def get_column_values(self, column: int) -> list:
        return self.sheet.col_values(column)

    def set_value(self, row: int, col: int, value: int | float | str):
        self.sheet.update_cell(row, col, value)

    def get_last_row(self):
        return self.sheet.get()[-1]
