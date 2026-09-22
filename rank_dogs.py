# Short Python script to rank dog breeds based on customizable criteria
# (e.g., intelligence, friendliness, trainability, grooming needs)

class DogBreed:
    def __init__(self, name, intelligence, friendliness, trainability, grooming):
        self.name = name
        self.intelligence = intelligence  # 1-10
        self.friendliness = friendliness  # 1-10
        self.trainability = trainability  # 1-10
        self.grooming = grooming          # 1-10 (higher = more maintenance)

    def calculate_score(self, weights):
        # Higher score is better; grooming is inverted (lower maintenance is preferred)
        score = (
            self.intelligence * weights.get('intelligence', 1.0) +
            self.friendliness * weights.get('friendliness', 1.0) +
            self.trainability * weights.get('trainability', 1.0) +
            (11 - self.grooming) * weights.get('grooming', 1.0)
        )
        return round(score, 2)


# Sample dog breeds database
breeds = [
    DogBreed("Border Collie", intelligence=10, friendliness=8, trainability=10, grooming=7),
    DogBreed("Golden Retriever", intelligence=9, friendliness=10, trainability=9, grooming=8),
    DogBreed("French Bulldog", intelligence=6, friendliness=9, trainability=6, grooming=3),
    DogBreed("German Shepherd", intelligence=9, friendliness=7, trainability=9, grooming=7),
    DogBreed("Poodle", intelligence=10, friendliness=8, trainability=10, grooming=9),
]

# Define weights for what matters most to you
user_weights = {
    'intelligence': 1.5,
    'friendliness': 2.0,
    'trainability': 1.5,
    'grooming': 1.0
}

# Rank breeds
ranked_breeds = sorted(breeds, key=lambda b: b.calculate_score(user_weights), reverse=True)

# Output results
print(f"{'Rank':<6}{'Breed':<20}{'Score':<8}")
print("-" * 34)
for i, breed in enumerate(ranked_breeds, 1):
    score = breed.calculate_score(user_weights)
    print(f"{i:<6}{breed.name:<20}{score:<8}")
