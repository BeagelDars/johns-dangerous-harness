import sys

def main():
    print("=== Carter Counter App ===")
    try:
        user_input = input("How many carters do you think you are? ")
        count = float(user_input)
        
        print(f"\nAnalyzing data... You are {count} carter pieces!")
        
        if count < 1:
            print("Status: Sub-carter. You need more carter energy.")
        elif count == 1:
            print("Status: Exactly one full Carter! Perfect balance.")
        else:
            print("Status: Overloaded with Carter energy! Maximum power achieved.")
            
    except ValueError:
        print("Error: Please enter a valid number (e.g., 1, 2.5, 42).")

if __name__ == "__main__":
    main()
