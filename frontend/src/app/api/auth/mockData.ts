// Mock user database - in a real app, this would be your actual database
export interface User {
  id: string;
  email: string;
  password: string; // In real apps, this would be hashed!
  name: string;
  createdAt: string;
}

export const mockUsers: User[] = [
  {
    id: "1",
    email: "demo@padly.com",
    password: "password123", // Never store plain text passwords in real apps!
    name: "Demo User",
    createdAt: "2024-01-01T00:00:00Z"
  },
  {
    id: "2", 
    email: "test@example.com",
    password: "test123",
    name: "Test User",
    createdAt: "2024-01-02T00:00:00Z"
  }
];

// Helper function to find user by email
export function findUserByEmail(email: string): User | undefined {
  return mockUsers.find(user => user.email.toLowerCase() === email.toLowerCase());
}

// Helper function to add new user (for signin/register)
export function addUser(email: string, password: string, name: string): User {
  const newUser: User = {
    id: (mockUsers.length + 1).toString(),
    email: email.toLowerCase(),
    password, // Again, hash this in real apps!
    name,
    createdAt: new Date().toISOString()
  };
  
  mockUsers.push(newUser);
  return newUser;
}

// Helper function to check if user already exists
export function userExists(email: string): boolean {
  return findUserByEmail(email) !== undefined;
}