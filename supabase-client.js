// supabase-client.js
// Shared Supabase client for the T-Rex Runner project.
// Import this file AFTER the Supabase CDN script tag.

const SUPABASE_URL  = 'https://pasffslberjhdhxikeuj.supabase.co';
const SUPABASE_ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBhc2Zmc2xiZXJqaGRoeGlrZXVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY3MzY0OTUsImV4cCI6MjEwMjMxMjQ5NX0.m1Kmh1k2y1yXE_-2y-cjbgDOIyMs8rJP14crWKyJ7Ts';

// NOTE: must use var (not const/let) so the client is attached to window
// and accessible from all other <script> tags on the page.
var supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON);
