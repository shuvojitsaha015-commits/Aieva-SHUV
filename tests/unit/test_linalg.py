"""Phase 6: vectors, matrices, eigen values, systems and complex numbers."""

from __future__ import annotations

import cmath
import math

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.figure import Figure

from aieva.core.errors import ParseError, SolveError
from aieva.plugins.math.complexnum import (
    argand_view,
    format_complex,
    parse_complex,
)
from aieva.plugins.math.linalg import (
    as_matrix,
    cube_view,
    eigen_values,
    eigen_view,
    matrix_view,
    parse_matrix,
    parse_system,
    parse_vectors,
    solve_system,
    system_view,
    vector_view,
)


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


# --------------------------------------------------------------------- vectors
def test_parse_vectors() -> None:
    vectors = parse_vectors("a=(1,2), b=(3,1)")
    assert [vector.name for vector in vectors] == ["a", "b"]
    assert vectors[0].values == [1.0, 2.0]
    assert vectors[1].dimension == 2


def test_parse_vectors_rejects_garbage() -> None:
    with pytest.raises(ParseError):
        parse_vectors("hello")
    with pytest.raises(ParseError):
        parse_vectors("a=(1,2,3,4)")


@pytest.mark.parametrize("operation", ["add", "subtract", "scale", "dot"])
def test_vector_operations_produce_figures(operation: str) -> None:
    import matplotlib.pyplot as plt

    result = vector_view("a=(1,2), b=(3,1)", operation=operation)
    try:
        assert isinstance(result.figure, Figure)
    finally:
        plt.close(result.figure)


def test_cross_product_needs_3d() -> None:
    with pytest.raises(SolveError):
        vector_view("a=(1,2), b=(3,1)", operation="cross")


def test_cross_product_in_3d() -> None:
    import matplotlib.pyplot as plt

    result = vector_view("a=(1,0,0), b=(0,1,0)", operation="cross")
    try:
        # the cross product of (1,0,0) and (0,1,0) is (0,0,1)
        assert "0. 0. 1." in result.meta["annotation"]
    finally:
        plt.close(result.figure)


# -------------------------------------------------------------------- matrices
def test_parse_matrix() -> None:
    matrix = parse_matrix("[[1,2],[3,4]]")
    assert matrix.shape == (2, 2)
    assert matrix[0, 1] == 2.0


def test_as_matrix_rejects_non_square() -> None:
    with pytest.raises(ParseError):
        as_matrix([[1, 2, 3], [4, 5, 6]])


def test_matrix_view_annotates_the_determinant() -> None:
    import matplotlib.pyplot as plt

    result = matrix_view(parse_matrix("[[2,0],[0,3]]"))
    try:
        assert result.meta["determinant"] == pytest.approx(6.0)
    finally:
        plt.close(result.figure)


def test_rotation_preset_has_a_unit_determinant() -> None:
    result = matrix_view(rotation=45.0)
    assert result.meta["determinant"] == pytest.approx(1.0, abs=1e-9)


def test_shear_preset_changes_the_determinant() -> None:
    result = matrix_view(shear=0.5)
    assert result.meta["determinant"] == pytest.approx(1.0, abs=1e-9)
    result = matrix_view(scale_x=2.0, scale_y=3.0)
    assert result.meta["determinant"] == pytest.approx(6.0, abs=1e-9)


def test_cube_view_needs_a_3x3_matrix() -> None:
    with pytest.raises(ParseError):
        cube_view([[1, 0], [0, 1]])
    result = cube_view([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    assert result.meta["determinant"] == pytest.approx(1.0)


# ----------------------------------------------------------------------- eigen
def test_eigenvalues_of_a_diagonal_matrix() -> None:
    values, _vectors = eigen_values(np.array([[2.0, 0.0], [0.0, 3.0]]))
    assert sorted(value.real for value in values) == pytest.approx([2.0, 3.0])


def test_rotation_by_90_degrees_has_complex_eigenvalues() -> None:
    values, _vectors = eigen_values(np.array([[0.0, -1.0], [1.0, 0.0]]))
    assert all(abs(value.imag) > 1e-9 for value in values)
    assert sorted(round(value.imag, 6) for value in values) == [-1.0, 1.0]


def test_eigen_view_warns_about_complex_eigenvalues() -> None:
    import matplotlib.pyplot as plt

    result = eigen_view([[0, -1], [1, 0]])
    try:
        assert result.meta["real_eigenvectors"] == 0
        assert result.meta["warnings"]
    finally:
        plt.close(result.figure)


def test_eigen_view_draws_real_eigenvectors() -> None:
    import matplotlib.pyplot as plt

    result = eigen_view([[2, 0], [0, 3]])
    try:
        assert result.meta["real_eigenvectors"] == 2
        assert result.meta["warnings"] == []
    finally:
        plt.close(result.figure)


# --------------------------------------------------------------------- systems
def test_parse_system() -> None:
    equations = parse_system("2x+y=5; x-y=1")
    assert len(equations) == 2


def test_system_with_a_known_solution() -> None:
    equations = parse_system("2x+y=5; x-y=1")
    solution = solve_system(equations)
    assert solution["type"] == "unique"
    assert solution["point"] == pytest.approx([2.0, 1.0])


def test_parallel_lines_have_no_solution() -> None:
    equations = parse_system("x+y=1; 2x+2y=5")
    solution = solve_system(equations)
    assert solution["type"] == "none"
    assert "no solution" in solution["explanation"].lower()


def test_identical_lines_have_infinite_solutions() -> None:
    equations = parse_system("x+y=1; 2x+2y=2")
    solution = solve_system(equations)
    assert solution["type"] == "infinite"


def test_system_view_marks_the_intersection() -> None:
    import matplotlib.pyplot as plt

    result = system_view("2x+y=5; x-y=1")
    try:
        assert result.meta["solution_type"] == "unique"
        assert result.meta["point"] == pytest.approx([2.0, 1.0])
    finally:
        plt.close(result.figure)


# --------------------------------------------------------------------- complex
def test_parse_complex() -> None:
    assert parse_complex("3 + 4i") == complex(3, 4)
    assert parse_complex("-2i") == complex(0, -2)
    assert parse_complex("5") == complex(5, 0)
    with pytest.raises(ParseError):
        parse_complex("hello")


def test_format_complex() -> None:
    assert format_complex(complex(3, 4)) == "3 + 4i"
    assert format_complex(complex(0, -2)) == "-2i"
    assert format_complex(complex(5, 0)) == "5"


def test_cube_roots_of_one_are_on_the_unit_circle() -> None:
    import matplotlib.pyplot as plt

    result = argand_view(complex(1, 0), operation="roots", n=3)
    try:
        annotation = result.meta["annotation"]
        assert "roots:" in annotation
        roots = [complex(cmath.exp(2j * math.pi * index / 3.0)) for index in range(3)]
        for root in roots:
            assert abs(abs(root) - 1.0) < 1e-9
    finally:
        plt.close(result.figure)


def test_argand_view_operations() -> None:
    import matplotlib.pyplot as plt

    for operation in ("none", "add", "multiply", "multiply_i", "conjugate", "power", "roots"):
        result = argand_view("3+4i", operation=operation, w="1+1i", n=3)
        try:
            assert isinstance(result.figure, Figure)
            assert result.meta["operation"] == operation
        finally:
            plt.close(result.figure)


def test_multiply_by_i_rotates_by_90_degrees() -> None:
    result = argand_view("1+0i", operation="multiply_i")
    assert result.meta["result"].startswith("1i") or result.meta["result"] == "0 + 1i"


def test_modulus_and_argument() -> None:
    result = argand_view("3+4i")
    assert result.meta["modulus"] == pytest.approx(5.0)
    assert result.meta["argument_deg"] == pytest.approx(math.degrees(math.atan2(4, 3)))
