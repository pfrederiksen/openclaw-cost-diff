class OpenclawCostDiff < Formula
  include Language::Python::Virtualenv

  desc "Compare OpenClaw token usage and API cost"
  homepage "https://github.com/pfrederiksen/openclaw-cost-diff"
  url "https://github.com/pfrederiksen/openclaw-cost-diff/archive/refs/tags/v0.1.2.tar.gz"
  sha256 "REPLACE_WITH_RELEASE_SHA256"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "openclaw-cost-diff", shell_output("#{bin}/openclaw-cost-diff --help")
  end
end
