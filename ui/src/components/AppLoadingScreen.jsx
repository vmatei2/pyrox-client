const AppLoadingScreen = ({ isExiting }) => {
  return (
    <div
      className={`bootstrap-screen${isExiting ? " is-exiting" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-busy="true"
      aria-labelledby="bootstrap-title"
      aria-label="Loading PYROX"
    >
      <div className="bootstrap-brand">
        <img
          src="/brand-wordmark.svg"
          alt="PYROX"
          className="bootstrap-wordmark"
          width="220"
          height="64"
        />
      </div>
      <p id="bootstrap-title" className="sr-only">
        Loading PYROX
      </p>
    </div>
  );
};

export default AppLoadingScreen;
