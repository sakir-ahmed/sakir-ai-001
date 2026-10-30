// Assert that the public proxy reaches dt-assistant rather than a generic 404 page.
// Use only a deliberately invalid verification token; no credentials are needed.
pm.test("Public webhook rejects an invalid verification token", function () {
  pm.response.to.have.status(403);
});
pm.test("Rejection comes from the intended application", function () {
  pm.expect(pm.response.json().detail).to.eql("verification failed");
});
