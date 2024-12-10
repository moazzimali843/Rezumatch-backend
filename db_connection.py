# import pyodbc

# class DatabaseConnection:
#     def __init__(self):
#         self.conn = None
#         self.cursor = None

#     def connect(self):
#         if not self.conn:
#             try:
#                 # Connection parameters
#                 server = 'localhost'
#                 database = 'tempdb'
#                 username = 'sa'
#                 password = 'Pakistan@123'

#                 # Establish the connection
#                 self.conn = pyodbc.connect(
#                     'DRIVER={ODBC Driver 17 for SQL Server};'
#                     'SERVER=' + server + ';'
#                     'DATABASE=' + database + ';'
#                     'UID=' + username + ';'
#                     'PWD=' + password + ';'
#                     'Connection Timeout=60;'
#                 )

#                 # Create a cursor object
#                 self.cursor = self.conn.cursor()

#                 print("Database connection established.")
#             except pyodbc.Error as e:
#                 print("Error occurred while connecting to the database:", e)

#     def close(self):
#         if self.conn:
#             self.conn.close()
#             print("Database connection closed.")
    
#     def commit(self):
#         if self.conn:
#             self.conn.commit()

# # Create an instance of the DatabaseConnection
# db = DatabaseConnection()
