// The data snapshot for this build's city, aliased in next.config.ts. Both cities'
// snapshots share Victoria's shape, so type it from Victoria's file.
declare module "@clubhub/snapshot" {
  const snapshot: typeof import("./data/demo-snapshot.json");
  export default snapshot;
}
