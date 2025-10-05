export default function Home() {
  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center', 
      justifyContent: 'center', 
      minHeight: '100vh',
      padding: '2rem'
    }}>
      <h1 style={{ fontSize: '3rem', marginBottom: '1rem' }}>
        Welcome to Padly
      </h1>
      <p style={{ fontSize: '1.25rem', color: '#666' }}>
        Your collaborative workspace is ready!
      </p>
    </div>
  );
}

