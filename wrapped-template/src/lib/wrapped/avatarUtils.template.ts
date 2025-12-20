/**
 * Avatar utility functions for {{PROJECT_NAME}} Wrapped
 * 
 * Replace this with your avatar/image handling logic
 */

/**
 * Get avatar URL for a user
 * @param username - Username to get avatar for
 * @returns Path to avatar image
 */
export function getAvatarForUser(username: string): string {
  // Customize this logic based on your avatar system
  // Examples:
  // - Static files: `/avatars/${username.toLowerCase().replace(/\s+/g, '_')}.png`
  // - API endpoint: `/api/avatars/${username}`
  // - Default fallback: `/avatars/default.png`
  
  const normalizedUsername = username
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_]/g, '');
  
  return `/avatars/${normalizedUsername}.png`;
}

/**
 * Get fallback avatar URL
 */
export function getDefaultAvatar(): string {
  return '/avatars/default.png';
}

