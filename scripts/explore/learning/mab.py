import numpy as np

# SRC: https://www.geeksforgeeks.org/multi-armed-bandit-problem-in-reinforcement-learning/

# Modeling OSmosis Design Space Exploration (ODSP) as an MAB optimization problem?

# No of arms: Could be one of:
#    * Resource Type
#    * Transition Type
#    * What about which exact resource
#

# How to move in the space:
#       Esentially take one of the transitions.
#
#

# Calculate Reward (How good is a point in the space):
#                 What                                      | How to Calculate      |   Comparable
#   ------------------------------------------------------------------------------------------------
#   Performance:                                            |                       |
#      * Not possible for every point                       | Run on CellulOS       | Always Yes. Integer
#   Isolation Metric:                                       |                       |
#      * Increasing Isolation via a certain type of path    | By tracking the path  | Only sometimes i.e., for adjacent points
#      * Fault Radius                                       | Graph Query           | Always Yes. Integer
#      * Resource Similarity Index                          | Graph Query           | Always Yes. Integer
#      * Trusted Computing Base                             | Graph Query           | Sometimes. When set is subset of another.
#      * Impact Boundary                                    | Graph Query           | Sometimes. When set is subset of another.
#      *
# Terminate:
#      The psuedo code is terminataing based on number of trials.
#      For ODSP, we can terminate:
#            if performance has gotten worse than a bound.
#            Isolation has increased, but is not increasing anymore.
#            This could happen as the number of trials we can do is restricted by the overall constraints (dubbed C1)
class EpsilonGreedy:
    def __init__(self, n_arms, epsilon):
        self.n_arms = n_arms
        self.epsilon = epsilon
        self.counts = np.zeros(n_arms)  # Number of times each arm is pulled
        self.values = np.zeros(n_arms)  # Estimated values of each arm

    def select_arm(self):
        if np.random.rand() < self.epsilon:
            return np.random.randint(0, self.n_arms)
        else:
            return np.argmax(self.values)

    def update(self, chosen_arm, reward):
        self.counts[chosen_arm] += 1
        n = self.counts[chosen_arm]
        value = self.values[chosen_arm]
        self.values[chosen_arm] = ((n - 1) / n) * value + (1 / n) * reward

# Example usage
n_arms = 10
epsilon = 0.1
n_trials = 10000
rewards = np.random.randn(n_arms, n_trials)  # Random rewards for demonstration

agent = EpsilonGreedy(n_arms, epsilon)
total_reward = 0

for t in range(n_trials):
    if t % 100 == 0:
        print("Total Reward:", total_reward)

    arm = agent.select_arm()
    reward = rewards[arm, t]
    agent.update(arm, reward)
    total_reward += reward

print("Total Reward:", total_reward)
