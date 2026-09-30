# Usage: ruby tools/make-manifest.rb <repo root>
# Reads VERSION, writes fieldbook-manifest.json (path => sha256 of the file with
# line endings normalised to LF, as update-fieldbook.ps1 computes it).
# Run before every release; commit the result with the change it describes.
require "json"
require "digest"

root = ARGV[0] or abort "usage: ruby tools/make-manifest.rb <repo root>"
Dir.chdir(root)

INCLUDE = [
  "AGENTS.md", "Features.md", "Cheat Sheet.md", "Using opencode.md", "SETUP.md",
  "CHANGELOG.md", "Dashboard.md", ".gitignore", "Templates/*.md",
  ".opencode/scripts/*", ".opencode/plugins/*", ".opencode/commands/*",
  ".opencode/migrations/*", "TaskNotes/Views/*.base",
]
EXCLUDE = ["Templates/Review-format.md", "TaskNotes/Views/*-default.base"]

version = File.read("VERSION").strip
abort "VERSION must look like 1.2.3" unless version.match?(/\A\d+\.\d+\.\d+\z/)

gather = ->(globs) { globs.flat_map { |g| Dir.glob(g, File::FNM_DOTMATCH) }.select { |f| File.file?(f) } }
paths = (gather.(INCLUDE) - gather.(EXCLUDE)).uniq.sort

hash = lambda do |p|
  t = File.binread(p).force_encoding("UTF-8").sub(/\A﻿/, "").gsub("\r\n", "\n")
  Digest::SHA256.hexdigest(t)
end

manifest = { "version" => version, "files" => paths.to_h { |p| [p, hash.(p)] } }
File.write("fieldbook-manifest.json", JSON.pretty_generate(manifest) + "\n")
puts "fieldbook-manifest.json: version #{version}, #{paths.size} files"
